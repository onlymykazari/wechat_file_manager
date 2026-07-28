# WeChat 文件管理器

一个用于 MacOS 系统的微信文件管理工具，通过创建集中存储和符号链接来实现文件去重和空间节省。

> 同时支持微信 Mac 4.x（数据目录 `xwechat_files`）和 3.x（数据目录 `2.0b4.0.9/<账号hash>/Message/MessageTemp`），通过配置中的 `sources` 多数据源机制实现，不存在的源会自动跳过。

## 主要功能

- 使用 MD5 哈希进行文件去重
- 为微信媒体文件创建集中存储
- 使用符号链接保持原始文件结构
- 可配置文件大小限制和跳过模式
- 可选择保留原始文件

## 安装方法

```bash
pip install git+https://github.com/zhoupc/wechat_file_manager.git
```

## 使用方法
1. 运行 `wfm init` 命令初始化配置文件

这一条命令会在主目录下创建一个名为`config_wechat_file_manager.yaml` 的文件，你可以根据自己的实际情况进行调整

```yaml 
paths:
  storage: ~/Documents/WeChatStorage  # 集中存储路径，各数据源存到 storage/<name>/ 子目录下
sources:
- name: wechat4                       # 微信 4.x，每个 wxid_xxx 目录对应一个账号
  root: ~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/
  target_folders:
  - msg/file                          # 聊天中收发的文件
  - msg/video                         # 聊天中收发的视频
- name: wechat3                       # 微信 3.x 遗留数据，每个账号hash目录对应一个账号
  root: ~/Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat/2.0b4.0.9/
  target_folders:
  - Message/MessageTemp               # 递归扫描其下所有会话的 Image/Video/Audio/File
  min_file_size: 0                    # 单源覆盖全局阈值（3.x 残留文件普遍较小）
settings:
  min_file_size: 1  # 全局最小文件大小，单位为MB，可被各源的同名字段覆盖
  preserve_originals: true # 是否保留原始文件，如果为false，会将文件替换为符号链接
  skip_patterns:    # 跳过模式，用于跳过某些文件夹或文件
  - pic_thumb
  - _thumb
  - .DS_Store
state:  
  last_run: null    # 上次运行时间，每次只处理该时间之后修改的文件
```

> 旧版单源配置（`paths.wechat` + `settings.target_folders`）仍然兼容，会被自动转换为单个数据源。
>
> 注意：微信 4.x 中聊天图片存放在 `msg/attach` 下，且已被加密为 `.dat` 格式，直接复制出来无法查看，因此默认不处理 4.x 图片；3.x 的图片/视频/语音是明文的，会正常处理。

2. 运行 `wfm run` 命令开始文件管理

## 联系
zhoupc1988@gmail.com