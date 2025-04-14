#!/usr/bin/env python3

import os
import argparse
import uvicorn

def main():
    parser = argparse.ArgumentParser(description='M3U8 录制服务')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='监听主机 (默认: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=3838, help='监听端口 (默认: 3838)')
    parser.add_argument('--downloads', type=str, default='downloads', help='下载目录 (默认: downloads)')
    
    args = parser.parse_args()
    
    os.environ['DOWNLOADS_DIR'] = args.downloads
    
    os.makedirs(args.downloads, exist_ok=True)
    
    print(f"启动 M3U8 录制服务在 http://{args.host}:{args.port}")
    print(f"下载目录: {os.path.abspath(args.downloads)}")
    
    # start
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=True)

if __name__ == "__main__":
    main()