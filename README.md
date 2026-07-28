# WeChat 文件管理器

一个用于 MacOS 系统的微信文件管理工具，通过创建集中存储和符号链接来实现文件去重和空间节省。

> 已适配微信 Mac 4.x 版本（数据目录 `xwechat_files`）。3.x 及更早版本请自行修改配置中的 `wechat` 路径和 `target_folders`。

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
  storage: ~/Documents/WeChatStorage  # 集中存储路径
  wechat: ~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/  # 微信 4.x 文件路径，其下每个 wxid_xxx 目录对应一个登录过的账号
settings:
  min_file_size: 1  # 最小文件大小，单位为MB
  preserve_originals: true # 是否保留原始文件，如果为false，会将文件替换为符号链接
  skip_patterns:    # 跳过模式，用于跳过某些文件夹或文件
  - pic_thumb
  - _thumb
  - .DS_Store
  target_folders:   # 只对以下文件夹进行管理（相对于每个账号目录）
  - msg/file        # 聊天中收发的文件
  - msg/video       # 聊天中收发的视频
state:  
  last_run: null    # 上次运行时间，每次只处理该时间之后修改的文件
```

> 注意：微信 4.x 中聊天图片存放在 `msg/attach` 下，且已被加密为 `.dat` 格式，直接复制出来无法查看，因此默认不处理图片。

2. 运行 `wfm run` 命令开始文件管理

## 联系
zhoupc1988@gmail.com