# 项目计划
name : 猫里奥全栈云图库web项目
# 功能实现+需求列举（暂定，后续还会继续添加）
**用户系统** ： 注册、登录、登出、获取当前用户
**私有空间** ： 每个用户都有一个私有空间，用于存储和管理自己的图片
**图片上传** ： 文件上传（Multipart）、URL 上传、自动 webp 压缩 + 缩略图
**图片管理** ： 图片列表、图片详情、图片删除、图片标签
# 当前暂时计划使用技术栈

**项目版本管理** ：Git（2.53.0.windows.1）

**后端** ：
Python管理与项目依赖管理 ：uv（版本0.11.14，已安装；用于管理项目依赖）
Web框架 ：FastAPI 
Web服务器 ：Uvicorn
数据库 ：MySQL（本地已安装，版本8.0.37，位于`C:\Program Files\MySQL\MySQL Server 8.0\`，服务已运行）
容器技术 ：Docker（版本29.5.2，已安装；用于运行 Redis，无需 Docker Hub 拉取）
缓存 ：Redis（7.4.9 (于Docker) ，每次在要使用redis的测试前都需确认容器 `redis` 有无启动运行）

**前端** ：
框架 ：Vue3 + TypeScript
构建 ：Vite
Node.js ：v22.13.0（已安装）