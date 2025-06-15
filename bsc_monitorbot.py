import os
import logging
import sqlite3
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import requests
from datetime import datetime, date
from dotenv import load_dotenv
import re

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")
MINIMUM_AMOUNT = float(os.getenv("MINIMUM_AMOUNT", 0.1))

# 初始化 SQLite 数据库
def init_db():
    try:
        conn = sqlite3.connect("monitor.db")
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS monitoring
                     (chat_id INTEGER PRIMARY KEY, address TEXT, last_tx_hash TEXT)''')
        conn.commit()
        logger.info("Database initialized successfully")
    except sqlite3.Error as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    finally:
        conn.close()

# 从数据库加载监控数据
def load_monitoring_data():
    try:
        conn = sqlite3.connect("monitor.db")
        c = conn.cursor()
        c.execute("SELECT chat_id, address, last_tx_hash FROM monitoring")
        data = c.fetchall()
        user_monitoring = {row[0]: row[1] for row in data if row[1]}
        last_tx_hashes = {row[0]: row[2] for row in data if row[2]}
        logger.info("Loaded monitoring data from database")
        return user_monitoring, last_tx_hashes
    except sqlite3.Error as e:
        logger.error(f"Failed to load monitoring data: {e}")
        return {}, {}
    finally:
        conn.close()

# 保存监控地址到数据库
def save_monitoring_data(chat_id, address, last_tx_hash=None):
    try:
        conn = sqlite3.connect("monitor.db")
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO monitoring (chat_id, address, last_tx_hash) VALUES (?, ?, ?)",
                  (chat_id, address, last_tx_hash))
        conn.commit()
        logger.info(f"Saved monitoring data for chat_id {chat_id}")
    except sqlite3.Error as e:
        logger.error(f"Failed to save monitoring data for chat_id {chat_id}: {e}")
    finally:
        conn.close()

# 删除监控数据
def delete_monitoring_data(chat_id):
    try:
        conn = sqlite3.connect("monitor.db")
        c = conn.cursor()
        c.execute("DELETE FROM monitoring WHERE chat_id = ?", (chat_id,))
        conn.commit()
        logger.info(f"Deleted monitoring data for chat_id {chat_id}")
    except sqlite3.Error as e:
        logger.error(f"Failed to delete monitoring data for chat_id {chat_id}: {e}")
    finally:
        conn.close()

# 验证 BSC 地址格式
def is_valid_bsc_address(address: str) -> bool:
    return bool(re.match(r'^0x[a-fA-F0-9]{40}$', address))

# 获取地址的最新交易哈希
def get_latest_tx_hash(address):
    try:
        url = "https://api.bscscan.com/api"
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "sort": "desc",
            "page": 1,
            "offset": 1,
            "apikey": BSCSCAN_API_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            logger.error(f"BscScan API request failed for {address}: Status {response.status_code}")
            return None

        data = response.json()
        if data.get("status") != "1":
            logger.error(f"BscScan API error for {address}: {data.get('message')}")
            return None

        transactions = data.get("result", [])
        if not transactions:
            logger.info(f"No transactions found for {address}")
            return None

        return transactions[0]["hash"]
    except requests.Timeout:
        logger.error(f"Timeout fetching latest transaction for {address}")
        return None
    except Exception as e:
        logger.error(f"Error fetching latest transaction for {address}: {e}")
        return None

# /start 命令处理程序，提供交互菜单
def start(update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("设置地址", callback_data='set')],
        [InlineKeyboardButton("停止监控", callback_data='stop')],
        [InlineKeyboardButton("查看状态", callback_data='status')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("请选择操作：", reply_markup=reply_markup)
    logger.info(f"User {update.message.chat_id} triggered /start command")

# 处理 InlineKeyboard 按钮的回调
def button_callback(update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    chat_id = query.message.chat_id
    data = query.data
    user_monitoring, _ = load_monitoring_data()

    if data == 'set':
        query.message.reply_text("请使用 /set <地址> 命令设置监控地址，例如：/set 0x1234567890abcdef...")
    elif data == 'stop':
        if chat_id in user_monitoring:
            delete_monitoring_data(chat_id)
            query.message.reply_text("已停止监控您的地址。")
            logger.info(f"User {chat_id} stopped monitoring via button")
        else:
            query.message.reply_text("您当前未设置任何监控地址。")
    elif data == 'status':
        address = user_monitoring.get(chat_id)
        if address:
            query.message.reply_text(f"当前监控地址：{address}\n最小交易金额：{MINIMUM_AMOUNT} BNB")
        else:
            query.message.reply_text("您当前未设置任何监控地址，请使用 /set 命令设置。")
        logger.info(f"User {chat_id} checked status via button")

# 设置监控地址
def set_address(update, context: CallbackContext):
    chat_id = update.message.chat_id
    args = update.message.text.split()

    if len(args) < 2:
        update.message.reply_text("请提供一个BSC地址，例如：/set 0x1234567890abcdef...")
        return

    address = args[1]
    if not is_valid_bsc_address(address):
        update.message.reply_text("无效的BSC地址，请检查格式（以0x开头，40位十六进制字符）！")
        return

    # 获取最新交易哈希，初始化监控
    latest_tx_hash = get_latest_tx_hash(address)
    save_monitoring_data(chat_id, address, latest_tx_hash)
    update.message.reply_text(f"已成功设置监控地址 {address}，将开始监控该地址的交易（金额 ≥ {MINIMUM_AMOUNT} BNB，仅限今天）。")
    logger.info(f"User {chat_id} set monitoring address: {address} with latest tx: {latest_tx_hash}")

# 停止监控
def stop_monitoring(update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_monitoring, _ = load_monitoring_data()
    if chat_id in user_monitoring:
        delete_monitoring_data(chat_id)
        update.message.reply_text("已停止监控您的地址。")
        logger.info(f"User {chat_id} stopped monitoring")
    else:
        update.message.reply_text("您当前未设置任何监控地址。")

# 查看监控状态
def status(update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_monitoring, _ = load_monitoring_data()
    address = user_monitoring.get(chat_id)
    if address:
        update.message.reply_text(f"当前监控地址：{address}\n最小交易金额：{MINIMUM_AMOUNT} BNB")
    else:
        update.message.reply_text("您当前未设置任何监控地址，请使用 /set 命令设置。")

# 检查所有用户的地址交易
def check_transactions(context: CallbackContext):
    user_monitoring, last_tx_hashes = load_monitoring_data()
    today = date.today()

    for chat_id, address in list(user_monitoring.items()):
        try:
            url = "https://api.bscscan.com/api"
            params = {
                "module": "account",
                "action": "txlist",
                "address": address,
                "sort": "desc",
                "page": 1,
                "offset": 10,
                "apikey": BSCSCAN_API_KEY
            }

            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                logger.error(f"BscScan API request failed for {address}: Status {response.status_code}")
                continue

            data = response.json()
            if data.get("status") != "1":
                logger.error(f"BscScan API error for {address}: {data.get('message')}")
                continue

            transactions = data.get("result", [])
            if not transactions:
                logger.info(f"No transactions found for {address}")
                continue

            latest_tx = transactions[0]["hash"]
            if last_tx_hashes.get(chat_id) == latest_tx:
                continue

            for tx in transactions:
                # 检查交易是否为今天
                tx_date = datetime.utcfromtimestamp(int(tx["timeStamp"])).date()
                if tx_date != today:
                    continue

                if last_tx_hashes.get(chat_id) == tx["hash"]:
                    break

                amount_bnb = int(tx["value"]) / 1e18
                if amount_bnb >= MINIMUM_AMOUNT:
                    tx_date_str = datetime.utcfromtimestamp(int(tx["timeStamp"])).strftime('%Y-%m-%d')
                    tx_time = datetime.utcfromtimestamp(int(tx["timeStamp"])).strftime('%H:%M:%S')
                    sender = tx["from"]
                    receiver = tx["to"]
                    tx_hash = tx["hash"]
                    tx_link = f"https://bscscan.com/tx/{tx_hash}"

                    message = (
                        f"检测到新交易！\n"
                        f"金额: {amount_bnb:.4f} BNB\n"
                        f"日期: {tx_date_str}\n"
                        f"时间: {tx_time}\n"
                        f"发送方: {sender}\n"
                        f"接收方: {receiver}\n"
                        f"交易哈希: {tx_hash}\n"
                        f"交易链接: {tx_link}"
                    )

                    context.bot.send_message(chat_id, message)
                    logger.info(f"Sent transaction notification to {chat_id} for tx {tx_hash}")

            save_monitoring_data(chat_id, address, latest_tx)

        except requests.Timeout:
            logger.error(f"Timeout checking transactions for {address}")
        except Exception as e:
            logger.error(f"Error checking transactions for {address} (Chat ID: {chat_id}): {e}")

def main():
    if not TELEGRAM_BOT_TOKEN or not BSCSCAN_API_KEY:
        logger.error("Missing TELEGRAM_BOT_TOKEN or BSCSCAN_API_KEY in .env file")
        raise EnvironmentError("请在 .env 文件中设置 TELEGRAM_BOT_TOKEN 和 BSCSCAN_API_KEY")

    # 调试：打印 MINIMUM_AMOUNT 的值
    logger.info(f"Loaded MINIMUM_AMOUNT: {MINIMUM_AMOUNT}")

    # 初始化数据库
    init_db()

    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # 注册命令
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("set", set_address))
    dp.add_handler(CommandHandler("stop", stop_monitoring))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CallbackQueryHandler(button_callback))

    # 每 30 秒检查一次交易
    updater.job_queue.run_repeating(check_transactions, interval=3, first=0)

    logger.info("Starting bot...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()