# m3u8-Recorder

这是一个基于Python的m3u8下载和录制服务，可以轻松下载网页视频或者录制直播，并保存为`.mp4`文件。

## 功能特点

- 通过Web界面管理下载任务
- 支持上传M3U8文件或提供URL创建下载任务
- 支持即时下载或定时录制功能
- 使用Docker进行简单部署
- 任务管理和状态监控

## 部署方法

### 使用Docker部署

```bash
docker pull yujzhu04/m3u8-recorder && docker run yujzhu04/m3u8-recorder -p 3838:3838 -v /path/to/downloads:/app/downloads m3u8-recorder
```
将`/path/to/downloads`替换为你希望存储下载文件的路径。

随后访问 http://localhost:3838 即可使用。

### 构建Docker镜像

```bash
git clone https://github.com/YuJ-ZHU/m3u8-Recorder.git
cd m3u8-Recorder
docker build -t m3u8-recorder .
```

然后，使用以下命令构建并运行容器：

```bash
docker run m3u8-recorder -p 3838:3838 -v /path/to/downloads:/app/downloads m3u8-recorder
```

随后访问 http://localhost:3838 即可使用。


## 贡献与支持

欢迎通过以下方式参与并改进项目：  
- **报告问题**：提交 [Issue](issues/new)，报告使用中遇到的问题或提出新的功能需求。
- **提交代码**：Fork → 提交 Pull Request，改进功能、修复bug或优化性能。
- **翻译改进**：帮助完善多语言支持。 
- **推广项目**：Star本项目，或者将本项目分享给更多人。