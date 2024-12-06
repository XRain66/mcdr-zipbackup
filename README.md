# MCDR-ZipBackup

> 本插件由 [PermanentBackup](https://github.com/TISUnion/PermanentBackup) 修改而来，感谢原作者的贡献！

![Version](https://img.shields.io/badge/version-10.27-blue)
![License](https://img.shields.io/github/license/XRain66/mcdr-zipbackup)
![MCDR Version](https://img.shields.io/badge/mcdr-2.0%2B-green)

一个可以定时永久备份Minecraft的MCDR插件

## ✨ 特性

- 🔄 多种备份模式
  - ⏱️ 间隔模式：自定义时间间隔（秒/分/时）
  - 📅 日期模式：每日/每周/每月定时备份
- 💾 压缩选项
  - 🚀 极速模式：最快的压缩速度
  - 📦 最佳模式：最高的压缩比
- 📝 备份管理
  - 支持备份注释
  - 备份列表查看
  - 实时进度显示
- ⚙️ 高级配置
  - 自定义备份路径
  - 多级权限控制
  - 自动保存控制

## 🚀 安装/使用

1. 安装依赖
```bash
pip install mcdreforged>=2.0.0
pip install apscheduler>=3.6.3
pip install tqdm>=4.65.0
```

2. 下载插件并放入 plugins 文件夹

3. 基本命令
```
!!zb help             # 显示帮助信息
!!zb make            # 创建备份
!!zb make <注释>     # 创建带注释的备份
!!zb list            # 查看最近的备份
!!zb listall         # 查看所有备份
```

## ⚙️ 配置

插件会在首次运行时自动创建配置文件，你可以在配置文件中修改以下选项：

```json
{
    "turn_off_auto_save": true,
    "ignore_session_lock": true,
    "backup_path": "./perma_backup",
    "server_path": "./server",
    "world_names": ["world"],
    "auto_backup_enabled": true,
    "auto_backup_mode": "interval",
    "auto_backup_interval": 3600,
    "auto_backup_unit": "s",
    "auto_backup_date_type": "daily",
    "compression_level": "best"  // "speed"(最快速度) 或 "best"(LZMA最佳压缩比)
}
```

## 📝 命令列表

### 基础命令
- `!!zb make [注释]` - 创建备份
- `!!zb list [数量]` - 查看备份列表
- `!!zb listall` - 查看所有备份

### 定时备份设置
- `!!zb auto on` - 开启自动备份
- `!!zb auto off` - 关闭自动备份
- `!!zb mode interval` - 切换到间隔模式
- `!!zb mode date` - 切换到日期模式
- `!!zb interval <时间> <单位>` - 设置备份间隔
- `!!zb date <类型>` - 设置备份日期类型 (daily/weekly/monthly)

### 高级设置
- `!!zb ziplevel <level>` - 设置压缩等级 (speed/best)
- `!!zb status` - 查看当前状态

## 🔒 权限设置

- 0级: 查看备份列表
- 2级: 创建备份、查看状态
- 3级: 所有配置操作

## 📄 许可证

[MIT License](LICENSE)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！