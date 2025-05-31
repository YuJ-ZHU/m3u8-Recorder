from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional, List, Dict, Any
from datetime import datetime, time
import os
import uuid
import json
import shutil
import m3u8
import requests
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from pydantic import BaseModel
import subprocess
import time as time_module
import re
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log")
    ]
)
logger = logging.getLogger("m3u8-recorder")

app = FastAPI(title="M3U8 录制服务")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

DOWNLOADS_DIR = os.environ.get("DOWNLOADS_DIR", "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

TASKS_FILE = "tasks.json"
tasks = {}

class Task(BaseModel):
    id: str
    name: str
    url: str
    status: str  # pending, running, completed, failed
    created_at: str
    scheduled_time: Optional[str] = None
    end_time: Optional[str] = None
    output_file: str
    type: str  # immediate, scheduled
    progress: Optional[float] = 0.0
    file_size: Optional[int] = 0
    duration: Optional[str] = None

scheduler = BackgroundScheduler()
scheduler.start()

def load_tasks():
    global tasks
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, 'r') as f:
                tasks = json.load(f)
                
            for task_id, task in tasks.items():
                if task["status"] == "pending" and task["type"] == "scheduled" and task["scheduled_time"]:
                    schedule_task(task_id, task["scheduled_time"], task.get("end_time"))
        except Exception as e:
            logger.error(f"加载任务失败: {e}")

def save_tasks():
    try:
        with open(TASKS_FILE, 'w') as f:
            json.dump(tasks, f)
    except Exception as e:
        logger.error(f"保存任务失败: {e}")

def download_m3u8(task_id: str):
    task = tasks.get(task_id)
    if not task:
        logger.error(f"任务 {task_id} 不存在")
        return
    
    try:
        tasks[task_id]["status"] = "running"
        tasks[task_id]["progress"] = 0.0
        save_tasks()
        
        url = task["url"]
        output_file = task["output_file"]
        output_path = os.path.join(DOWNLOADS_DIR, output_file)
        
        logger.info(f"开始下载: {url} 到 {output_path}")
        
        cmd = [
            "ffmpeg", "-y", "-i", url, 
            "-c", "copy", "-bsf:a", "aac_adtstoasc", 
            "-progress", "pipe:1",
            output_path
        ]
        
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
            universal_newlines=True, bufsize=1
        )
        
        # 启动进度监控线程
        progress_thread = threading.Thread(
            target=monitor_progress, 
            args=(process, task_id)
        )
        progress_thread.start()
        
        stdout, stderr = process.communicate()
        progress_thread.join()
        
        if process.returncode != 0:
            logger.error(f"下载失败: {stderr}")
            tasks[task_id]["status"] = "failed"
        else:
            logger.info(f"下载完成: {output_path}")
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["progress"] = 100.0
            
            # 获取文件大小
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                tasks[task_id]["file_size"] = file_size
            
        save_tasks()
    except Exception as e:
        logger.error(f"下载过程中出错: {e}")
        tasks[task_id]["status"] = "failed"
        save_tasks()

def monitor_progress(process, task_id):
    """监控ffmpeg进度"""
    duration_pattern = re.compile(r'duration=([\d:.]+)')
    time_pattern = re.compile(r'out_time=([\d:.]+)')
    total_duration = None
    
    try:
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
                
            # 解析总时长
            if total_duration is None:
                duration_match = duration_pattern.search(line)
                if duration_match:
                    duration_str = duration_match.group(1)
                    total_duration = parse_time_to_seconds(duration_str)
                    tasks[task_id]["duration"] = duration_str
            
            # 解析当前进度
            time_match = time_pattern.search(line)
            if time_match and total_duration and total_duration > 0:
                current_time_str = time_match.group(1)
                current_time = parse_time_to_seconds(current_time_str)
                progress = min((current_time / total_duration) * 100, 100)
                tasks[task_id]["progress"] = round(progress, 1)
                save_tasks()
                
    except Exception as e:
        logger.error(f"监控进度时出错: {e}")

def parse_time_to_seconds(time_str):
    """将时间字符串转换为秒数"""
    try:
        parts = time_str.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        elif len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        else:
            return float(time_str)
    except:
        return 0

def schedule_task(task_id: str, start_time: str, end_time: Optional[str] = None):
    try:
        start_dt = datetime.fromisoformat(start_time)
        
        start_trigger = DateTrigger(run_date=start_dt)
        
        job_id = f"start_{task_id}"
        scheduler.add_job(
            download_m3u8, 
            trigger=start_trigger, 
            args=[task_id], 
            id=job_id,
            replace_existing=True
        )
        
        logger.info(f"已调度任务 {task_id} 在 {start_time} 开始")
        
        if end_time:
            end_dt = datetime.fromisoformat(end_time)
            end_trigger = DateTrigger(run_date=end_dt)
            
            def stop_recording(task_id):
                pass
            
            scheduler.add_job(
                stop_recording, 
                trigger=end_trigger, 
                args=[task_id], 
                id=f"stop_{task_id}",
                replace_existing=True
            )
            
            logger.info(f"已调度任务 {task_id} 在 {end_time} 结束")
    
    except Exception as e:
        logger.error(f"调度任务失败: {e}")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/tasks")
async def create_task(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    task_type: str = Form(...),  # immediate, scheduled
    scheduled_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None)
):
    try:
        if not url and not file:
            raise HTTPException(status_code=400, detail="必须提供URL或上传M3U8文件")
        
        if task_type == "scheduled" and not scheduled_time:
            raise HTTPException(status_code=400, detail="定时任务必须提供开始时间")
        
        task_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        output_file = f"{name.replace(' ', '_')}_{timestamp}.mp4"
        
        if file:
            temp_file = f"temp_{task_id}.m3u8"
            with open(temp_file, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            m3u8_obj = m3u8.load(temp_file)
            if m3u8_obj.is_variant:
                url = m3u8_obj.playlists[0].uri
            else:
                base_url = os.path.dirname(file.filename)
                url = f"{base_url}/{temp_file}"
            
            os.remove(temp_file)
        
        new_task = {
            "id": task_id,
            "name": name,
            "url": url,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "output_file": output_file,
            "type": task_type
        }
        
        if task_type == "scheduled":
            new_task["scheduled_time"] = scheduled_time
            if end_time:
                new_task["end_time"] = end_time
        
        tasks[task_id] = new_task
        save_tasks()
        
        if task_type == "immediate":
            background_tasks.add_task(download_m3u8, task_id)
        else:
            schedule_task(task_id, scheduled_time, end_time)
        
        return JSONResponse(content={"task_id": task_id, "message": "任务创建成功"})
    
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks")
async def get_tasks():
    return JSONResponse(content=list(tasks.values()))

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return JSONResponse(content=task)

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    try:
        scheduler.remove_job(f"start_{task_id}")
        scheduler.remove_job(f"stop_{task_id}")
    except:
        pass
    
    del tasks[task_id]
    save_tasks()
    
    return JSONResponse(content={"message": "任务已删除"})

@app.delete("/api/tasks/{task_id}/file")
async def delete_task_file(task_id: str):
    """删除任务对应的视频文件"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks[task_id]
    output_file = task["output_file"]
    file_path = os.path.join(DOWNLOADS_DIR, output_file)
    
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"已删除文件: {file_path}")
            return JSONResponse(content={"message": "文件已删除"})
        else:
            raise HTTPException(status_code=404, detail="文件不存在")
    except Exception as e:
        logger.error(f"删除文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")

@app.get("/api/tasks/{task_id}/progress")
async def get_task_progress(task_id: str):
    """获取任务进度"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks[task_id]
    return JSONResponse(content={
        "task_id": task_id,
        "status": task["status"],
        "progress": task.get("progress", 0),
        "duration": task.get("duration"),
        "file_size": task.get("file_size", 0)
    })

@app.on_event("startup")
def startup_event():
    load_tasks()

@app.on_event("shutdown")
def shutdown_event():
    save_tasks()
    scheduler.shutdown()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=3838, reload=True)