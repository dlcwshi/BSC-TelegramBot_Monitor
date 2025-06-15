BSC 交易监控 Telegram 机器人

项目概述

这是一个 Telegram 机器人，用于监控 Binance Smart Chain (BSC) 地址的交易活动。当监控的地址发生金额大于或等于指定阈值（默认 0.1 BNB）的交易时，机器人会通过 Telegram 发送通知。项目使用 SQLite 数据库存储用户监控数据，通过 BscScan API 获取交易信息。

主要功能


设置监控：通过 /set <BSC地址> 命令设置要监控的地址。

交易通知：监控当天交易，金额 ≥ 指定阈值时发送通知（包括金额、时间、发送方、接收方、交易哈希和链接）。

交互菜单：通过 /start 提供设置、停止和查看状态的按钮。

停止监控：通过 /stop 停止监控。

状态查询：通过 /status 查看当前监控地址和阈值。

数据持久化：使用 SQLite 存储监控数据。



技术栈

语言：Python 3

库：python-telegram-bot, requests, python-dotenv, sqlite3

API：BscScan API

安装步骤





克隆项目：

git clone  https://github.com/dlcwshi/BSC-TelegramBot_Monitor.git


安装依赖：

pip install python-telegram-bot==13.7 requests==2.28.1 python-dotenv==0.21.0


配置环境变量： 在项目根目录创建 .env 文件，添加：

TELEGRAM_BOT_TOKEN=<您的Telegram Bot Token>
BSCSCAN_API_KEY=<您的BscScan API Key>
MINIMUM_AMOUNT=0.1

从 BotFather 获取 Telegram Bot Token。

从 BscScan 获取 API Key。



运行：

python bsc_monitorbot.py



使用方法

在 Telegram 中与机器人交互：

/start：显示交互菜单。

/set <地址>：设置监控地址（例：/set 0x1234567890abcdef...）。

/stop：停止监控。

/status：查看监控状态。


机器人每 30 秒检查交易，发送符合条件的通知。



注意事项

确保 .env 文件正确配置。

BSC 地址需为 0x 开头的 40 位十六进制字符。

BscScan API 有速率限制，建议合理设置检查间隔。




日志

日志以 INFO 级别记录关键操作和错误，输出格式为：时间 - 名称 - 级别 - 消息。

