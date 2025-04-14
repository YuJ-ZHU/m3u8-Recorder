import os
import logging
import subprocess
import requests
import m3u8
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger("m3u8-recorder")

class M3U8Downloader:
    
    def __init__(self, downloads_dir: str):
        self.downloads_dir = downloads_dir
        os.makedirs(downloads_dir, exist_ok=True)
    
    def validate_m3u8_url(self, url: str) -> bool:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return False
                
            content = response.text
            if not content.strip().startswith('#EXTM3U'):
                return False
                
            return True
        except Exception as e:
            logger.error(f"验证M3U8 URL失败: {e}")
            return False
    
    def download(self, url: str, output_file: str, task_id: str) -> Dict[str, Any]:
        result = {
            "success": False,
            "message": "",
            "output_path": "",
            "duration": 0
        }
        
        try:
            output_path = os.path.join(self.downloads_dir, output_file)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            logger.info(f"开始下载: {url} 到 {output_path}")
            start_time = datetime.now()
            
            cmd = [
                "ffmpeg", "-y", "-i", url, 
                "-c", "copy", "-bsf:a", "aac_adtstoasc", 
                output_path
            ]
            
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            
            stdout, stderr = process.communicate()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            if process.returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"下载失败: {error_msg}")
                result["message"] = f"下载失败: {error_msg[:200]}..."
                return result
            
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                result["message"] = "下载完成，但文件为空或不存在"
                return result
            
            logger.info(f"下载完成: {output_path}, 耗时: {duration:.2f}秒")
            result["success"] = True
            result["message"] = "下载成功"
            result["output_path"] = output_path
            result["duration"] = duration
            
            return result
            
        except Exception as e:
            logger.error(f"下载过程中出错: {e}")
            result["message"] = f"下载过程中出错: {str(e)}"
            return result
    
    def record(self, url: str, output_file: str, task_id: str, duration: Optional[int] = None) -> Dict[str, Any]:
        result = {
            "success": False,
            "message": "",
            "output_path": "",
            "duration": 0
        }
        
        try:
            output_path = os.path.join(self.downloads_dir, output_file)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            logger.info(f"开始录制: {url} 到 {output_path}")
            start_time = datetime.now()
            
            cmd = ["ffmpeg", "-y", "-i", url]
            
            if duration:
                cmd.extend(["-t", str(duration)])
            
            cmd.extend(["-c", "copy", "-bsf:a", "aac_adtstoasc", output_path])
            
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            
            self.recording_processes[task_id] = process
            
            stdout, stderr = process.communicate()
            
            if task_id in self.recording_processes:
                del self.recording_processes[task_id]
            
            end_time = datetime.now()
            actual_duration = (end_time - start_time).total_seconds()
            
            if process.returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"录制失败: {error_msg}")
                result["message"] = f"录制失败: {error_msg[:200]}..."
                return result
            
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                result["message"] = "录制完成，但文件为空或不存在"
                return result
            
            logger.info(f"录制完成: {output_path}, 耗时: {actual_duration:.2f}秒")
            result["success"] = True
            result["message"] = "录制成功"
            result["output_path"] = output_path
            result["duration"] = actual_duration
            
            return result
            
        except Exception as e:
            logger.error(f"录制过程中出错: {e}")
            result["message"] = f"录制过程中出错: {str(e)}"
            return result
    
    def stop_recording(self, task_id: str) -> bool:
        if task_id not in self.recording_processes:
            logger.warning(f"任务 {task_id} 不在录制中或已结束")
            return False
        
        try:
            process = self.recording_processes[task_id]
            process.terminate()
            logger.info(f"已停止录制任务: {task_id}")
            return True
        except Exception as e:
            logger.error(f"停止录制任务失败: {e}")
            return False
    
    def parse_m3u8_file(self, file_path: str) -> Dict[str, Any]:
        result = {
            "success": False,
            "message": "",
            "is_variant": False,
            "playlists": [],
            "segments": [],
            "duration": 0
        }
        
        try:
            playlist = m3u8.load(file_path)
            
            result["success"] = True
            result["is_variant"] = playlist.is_variant
            
            if playlist.is_variant:
                result["playlists"] = [
                    {"uri": p.uri, "bandwidth": p.stream_info.bandwidth}
                    for p in playlist.playlists
                ]
            else:
                result["segments"] = [
                    {"uri": s.uri, "duration": s.duration}
                    for s in playlist.segments
                ]
                result["duration"] = playlist.target_duration * len(playlist.segments) if playlist.target_duration else sum(s.duration for s in playlist.segments)
            
            return result
            
        except Exception as e:
            logger.error(f"解析M3U8文件失败: {e}")
            result["message"] = f"解析M3U8文件失败: {str(e)}"
            return result
    
    recording_processes = {}