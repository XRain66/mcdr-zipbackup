import collections
import os
import shutil
import time
import zipfile
import threading
from threading import Lock, Event
from typing import List, Dict, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import json
from tqdm import tqdm

from mcdreforged.api.all import *


class Configure(Serializable):
    turn_off_auto_save: bool = True
    ignore_session_lock: bool = True
    backup_path: str = './perma_backup'
    server_path: str = './server'
    world_names: List[str] = [
        'world'
    ]
    # 自动备份相关配置
    auto_backup_enabled: bool = True  # 是否启用自动备份
    auto_backup_mode: str = 'interval'  # 备份模式: 'interval' 或 'date'
    # 间隔模式配置
    auto_backup_interval: int = 3600  # 自动备份时间间隔，默认 3600 秒（1 小时）
    auto_backup_unit: str = 's'  # 时间单位，可选值：'s', 'm', 'h', 'd'
    # 日期模式配置
    auto_backup_date_type: str = 'daily'  # 日期类型：'monthly', 'weekly', 'daily'
    compression_level: str = 'best'  # 压缩等级：'speed' 或 'best'

    minimum_permission_level: Dict[str, int] = {
        'make': 2,
        'list': 0,
        'listall': 2,
        'stats': 0,
        'time.enable': 3,
        'time.disable': 3,
        'time.interval': 3,
        'time.date': 3,
        'time.change': 3,
        'ziplevel': 3
    }

    def get_compression_method(self) -> int:
        """获取实际的压缩方法"""
        return zipfile.ZIP_STORED if self.compression_level == 'speed' else zipfile.ZIP_LZMA

    def save(self):
        config_file_path = os.path.join('config', 'zip_backup.json')
        with open(config_file_path, 'w', encoding='utf-8') as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=4)


auto_backup_timer = None  # 定时器引用，用于取消任务

config: Configure
Prefix = '!!zb'
CONFIG_FILE = os.path.join('config', 'zip_backup.json')
HelpMessage = '''
§b ______  _         ____                  _                
§b|__  / |(_)_ __   | __ )    __ _   ___ | | __ _   _ _ __  
§b  / /  | | '_ \   |  _ \   / _` | / __|| |/ /| | | | '_ \ 
§b / /_  | | |_) |  | |_) | | (_| || (__ |   < | |_| | |_) |
§b/____| |_| .__/   |____/   \__,_| \___||_|\_\ \__,_| .__/ 
§b         |_|                                        |_|    §6by XRain666§r
§e ---------------------- v10.27 ---------------------- §r
§7{0} make [<注释>]§r 创建一个备份
§7{0} list§r 列出最近10个备份
§7{0} listall§r 列出所有备份
§7{0} stats§r 显示备份状态信息
§7{0} ziplevel <等级>§r §r设置压缩等级。§7[<等级>]§r可选speed(最快速度),best(最佳压缩比)
§7{0} time enable§r 启动自动备份
§7{0} time disable§r 关闭自动备份
§7{0} time interval <时间间隔> <单位>§r §r设置自动备份时间间隔。§7[<单位>]§r可选s(秒）,m(分）,h(时),d(天)
§7{0} time date <类型>§r §r设置自动备份日期类型。§7[<类型>]§r可选monthly(每月),weekly(每周),daily(每天)
§7{0} time change <模式>§r §r切换备份模式。§7[<模式>]§r可选interval(间隔),date(日期)
§a小草神什么的最可爱拉！(◕ᴗ◕✿)§r
'''.strip().format(Prefix)
game_saved = False
plugin_unloaded = False
creating_backup = Lock()
scheduler = None
server_inst = None

# 插件加载时显示的字符画
PLUGIN_LOADED_ART = r'''
§b ______  _         ____                  _                
§b|__  / |(_)_ __   | __ )    __ _   ___ | | __ _   _ _ __  
§b  / /  | | '_ \   |  _ \   / _` | / __|| |/ /| | | | '_ \ 
§b / /_  | | |_) |  | |_) | | (_| || (__ |   < | |_| | |_) |
§b/____| |_| .__/   |____/   \__,_| \___||_|\_\ \__,_| .__/ §6by XRain666§r
§b         |_|                                        |_|    §r
§e ---------------------- v10.27 ---------------------- §r
'''

'''
mcdr_root/
	server/
		world/
	perma_backup/
		backup_2020-04-29_20-08-11_comment.zip
'''


def info_message(source: CommandSource, msg: str, broadcast=False):
    for line in msg.splitlines():
        text = '[zip_backup] ' + line
        if broadcast and source.is_player:
            source.get_server().broadcast(text)
        else:
            source.reply(text)


def touch_backup_folder():
    if not os.path.isdir(config.backup_path):
        os.makedirs(config.backup_path)


def zip_world(server: ServerInterface, comment: Optional[str] = None):
    """压缩世界文件"""
    # 获取总文件大小和数量
    total_size = 0
    file_count = 0
    for world in config.world_names:
        world_path = os.path.join(config.server_path, world)
        if not os.path.exists(world_path):
            continue
        for root, _, files in os.walk(world_path):
            for file in files:
                # 跳过 session.lock 文件
                if file == 'session.lock':
                    continue
                file_path = os.path.join(root, file)
                if os.path.exists(file_path):
                    try:
                        total_size += os.path.getsize(file_path)
                        file_count += 1
                    except OSError:
                        continue

    # 准备压缩
    timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
    zip_file = os.path.join(config.backup_path, f'backup_{timestamp}.zip')
    
    # 确保备份目录存在
    try:
        os.makedirs(config.backup_path, exist_ok=True)
    except PermissionError as e:
        server.logger.error(f"无法创建备份目录: {str(e)}")
        raise

    # 创建进度条
    progress = tqdm(total=total_size, unit='B', unit_scale=True, 
                   desc='压缩进度', ncols=100, 
                   bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]')

    try:
        with zipfile.ZipFile(zip_file, 'w', config.get_compression_method()) as zf:
            # 添加注释
            if comment:
                zf.comment = comment.encode()

            # 遍历所有世界文件夹
            for world in config.world_names:
                world_path = os.path.join(config.server_path, world)
                if not os.path.exists(world_path):
                    continue

                for root, _, files in os.walk(world_path):
                    for file in files:
                        # 跳过 session.lock 文件
                        if file == 'session.lock':
                            continue
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path):
                            try:
                                # 计算相对路径
                                arcname = os.path.relpath(file_path, config.server_path)
                                # 写入文件并更新进度条
                                zf.write(file_path, arcname)
                                progress.update(os.path.getsize(file_path))
                            except (OSError, PermissionError) as e:
                                server.logger.warning(f"跳过文件 {file_path}: {str(e)}")
                                continue

    except Exception as e:
        # 如果压缩失败，删除未完成的文件
        try:
            if os.path.exists(zip_file):
                os.remove(zip_file)
        except:
            pass
        raise
    finally:
        progress.close()


@new_thread('Zip-Backup')
def create_backup(source: CommandSource, context: dict):
    """创建备份"""
    comment = context.get('cmt', None)
    global creating_backup
    acquired = creating_backup.acquire(blocking=False)
    auto_save_on = True
    if not acquired:
        info_message(source, '§c正在备份中，请不要重复输入§r')
        return
    try:
        info_message(source, '备份中...请稍等', broadcast=True)
        start_time = time.time()

        # save world
        if config.turn_off_auto_save:
            source.get_server().execute('save-off')
            auto_save_on = False
        global game_saved
        game_saved = False
        source.get_server().execute('save-all flush')
        while True:
            time.sleep(0.01)
            if game_saved:
                break
            if plugin_unloaded:
                source.reply('§c插件卸载，备份中断！§r', broadcast=True)
                if not auto_save_on:
                    source.get_server().execute('save-on')
                creating_backup.release()
                return

        try:
            # zipping worlds
            timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
            zip_file_name = os.path.join(config.backup_path, f'backup_{timestamp}.zip')
            
            # 确保备份目录存在并有写入权限
            os.makedirs(config.backup_path, exist_ok=True)
            
            info_message(source, f'创建压缩文件§e{os.path.basename(zip_file_name)}§r中...', broadcast=True)
            zip_world(source.get_server(), comment)
            
            info_message(source, '备份§a完成§r，耗时{}秒'.format(round(time.time() - start_time, 1)), broadcast=True)
            
        except PermissionError as e:
            info_message(source, f'§c权限错误：无法写入备份文件，请检查目录权限: {str(e)}§r', broadcast=True)
            source.get_server().logger.error(f'备份失败：权限错误 - {str(e)}')
        except Exception as e:
            info_message(source, f'§c备份失败：{str(e)}§r', broadcast=True)
            source.get_server().logger.exception('创建备份失败')
            
    finally:
        if not auto_save_on:
            source.get_server().execute('save-on')
        if creating_backup.locked():
            creating_backup.release()


def list_backup(source: CommandSource, context: dict, *, amount=10):
    try:
        amount = context.get('amount', amount)
        touch_backup_folder()
        arr = []
        for name in os.listdir(config.backup_path):
            file_name = os.path.join(config.backup_path, name)
            if os.path.isfile(file_name) and file_name.endswith('.zip'):
                arr.append(collections.namedtuple('T', 'name stat')(os.path.basename(file_name)[: -len('.zip')], os.stat(file_name)))
        arr.sort(key=lambda x: x.stat.st_mtime, reverse=True)
        info_message(source, '共有§6{}§r个备份'.format(len(arr)))
        if amount == -1:
            amount = len(arr)
        for i in range(min(amount, len(arr))):
            source.reply('§7{}.§r §e{} §r{}MB'.format(i + 1, arr[i].name, round(arr[i].stat.st_size / 2 ** 20, 1)))
    except Exception as e:
        source.reply(f'§c列出备份时发生错误: {str(e)}§r')
        source.get_server().logger.exception('列出备份时发生错误')


def get_backup_interval_in_seconds() -> int:
    """将自动备份间隔转换为秒"""
    unit = config.auto_backup_unit.lower()
    if unit == 'm':
        return config.auto_backup_interval * 60
    elif unit == 'h':
        return config.auto_backup_interval * 3600
    elif unit == 'd':
        return config.auto_backup_interval * 86400
    else:  # 默认为秒
        return config.auto_backup_interval


def auto_backup_task(server: PluginServerInterface):
    """执行自动备份任务"""
    try:
        source = server.get_plugin_command_source()
        info_message(source, '自动备份中……', broadcast=True)
        create_backup(source, {})
    except Exception as e:
        server.logger.error(f'自动备份失败: {str(e)}')
        server.logger.exception('自动备份详细错误信息：')
        try:
            source = server.get_plugin_command_source()
            info_message(source, f'§c自动备份失败§r: {str(e)}', broadcast=True)
        except:
            pass


def start_auto_backup(server: PluginServerInterface):
    """启动自动备份任务"""
    global scheduler
    if scheduler is None:
        scheduler = BackgroundScheduler()
        scheduler.start()

    # 移除现有的定时任务（如果有）
    if scheduler.get_job("auto_backup_task"):
        scheduler.remove_job("auto_backup_task")

    # 根据备份模式设置定时任务
    if config.auto_backup_mode == 'interval':
        # 计算间隔秒数
        interval = config.auto_backup_interval
        if config.auto_backup_unit == 'm':
            interval *= 60
        elif config.auto_backup_unit == 'h':
            interval *= 3600
        elif config.auto_backup_unit == 'd':
            interval *= 86400
        
        # 添加间隔模式的定时任务
        scheduler.add_job(
            auto_backup_task,
            'interval',
            seconds=interval,
            id="auto_backup_task",
            args=[server_inst]
        )
    else:  # date mode
        # 根据类型设置cron表达式
        if config.auto_backup_date_type == 'monthly':
            cron = '0 1 1 * *'  # 每月1日凌晨1点
        elif config.auto_backup_date_type == 'weekly':
            cron = '0 1 * * 1'  # 每周一凌晨1点
        else:  # daily
            cron = '0 1 * * *'  # 每天凌晨1点
        
        # 添加日期模式的定时任务
        scheduler.add_job(
            auto_backup_task,
            CronTrigger.from_crontab(cron),
            id="auto_backup_task",
            args=[server_inst]
        )


def stop_auto_backup():
    """停止自动备份任务"""
    global scheduler
    if scheduler:
        scheduler.shutdown()
        scheduler = None


def on_info(server, info):
    if not info.is_user:
        if info.content == 'Saved the game':
            global game_saved
            game_saved = True


def update_backup_interval():
    global scheduler
    if scheduler:
        scheduler.remove_all_jobs()
        
        if config.auto_backup_enabled:
            if config.auto_backup_mode == 'interval':
                # 间隔模式
                seconds = get_backup_interval_in_seconds()
                scheduler.add_job(
                    auto_backup_task,
                    'interval',
                    seconds=seconds,
                    id='auto_backup_task',
                    args=[server_inst]
                )
            else:
                # 日期模式
                if config.auto_backup_date_type == 'monthly':
                    # 每月1号凌晨1点
                    scheduler.add_job(
                        auto_backup_task,
                        'cron',
                        day='1',
                        hour='1',
                        minute='0',
                        id='auto_backup_task',
                        args=[server_inst]
                    )
                elif config.auto_backup_date_type == 'weekly':
                    # 每周一凌晨1点
                    scheduler.add_job(
                        auto_backup_task,
                        'cron',
                        day_of_week='mon',
                        hour='1',
                        minute='0',
                        id='auto_backup_task',
                        args=[server_inst]
                    )
                else:  # daily
                    # 每天凌晨1点
                    scheduler.add_job(
                        auto_backup_task,
                        'cron',
                        hour='1',
                        minute='0',
                        id='auto_backup_task',
                        args=[server_inst]
                    )


def set_backup_date(source: CommandSource, context: dict):
    """设置按日期备份"""
    date_type = context.get('type', '').lower()
    if date_type not in ['monthly', 'weekly', 'daily']:
        source.reply('§c日期类型必须是monthly/weekly/daily中的一个§r')
        return

    config.auto_backup_date_type = date_type
    config.auto_backup_mode = 'date'  # 自动切换到日期模式
    config.save()

    # 更新定时任务
    update_backup_interval()

    # 显示成功消息
    type_names = {'monthly': '每月', 'weekly': '每周', 'daily': '每天'}
    source.reply(f'§a已将备份时间设置为{type_names[date_type]}凌晨1点§r')


def change_backup_mode(source: CommandSource, context: dict):
    """切换备份模式"""
    mode = context['mode']
    if mode not in ['interval', 'date']:
        source.reply('§c无效的备份模式，可选值：interval(间隔), date(日期)§r')
        return
    
    # 如果模式没有变化，直接返回
    if config.auto_backup_mode == mode:
        source.reply(f'§e当前已经是{mode}模式了§r')
        return
    
    # 更新配置
    config.auto_backup_mode = mode
    config.save()
    
    # 如果自动备份已启用，重新设置定时任务
    if config.auto_backup_enabled:
        start_auto_backup(server_inst)
    
    source.reply(f'§a已切换至{mode}模式§r')
    # 显示当前配置
    show_backup_stats(source)


def enable_auto_backup(source: CommandSource, server: PluginServerInterface):
    """启用自动备份"""
    config.auto_backup_enabled = True
    config.save()  # 保存配置
    start_auto_backup(server)
    source.reply('§a已启用自动备份§r')


def disable_auto_backup(source: CommandSource, server: PluginServerInterface):
    """禁用自动备份"""
    config.auto_backup_enabled = False
    config.save()  # 保存配置
    stop_auto_backup()
    source.reply('§c已禁用自动备份§r')


def set_backup_interval(source: CommandSource, context: dict):
    """设置自动备份时间间隔"""
    interval = context['time']
    unit = context['unit']
    if unit not in ['s', 'm', 'h', 'd']:
        source.reply('§c无效的时间单位，可选值：s(秒), m(分), h(时), d(天)§r')
        return

    # 更新配置
    config.auto_backup_interval = interval
    config.auto_backup_unit = unit
    config.auto_backup_mode = 'interval'  # 自动切换到间隔模式
    config.save()

    # 如果自动备份已启用，重新设置定时任务
    if config.auto_backup_enabled:
        start_auto_backup(server_inst)

    source.reply(f'§a已设置自动备份间隔为{interval}{unit}§r')
    # 显示当前配置
    show_backup_stats(source)


def set_backup_date(source: CommandSource, context: dict):
    """设置自动备份日期类型"""
    backup_type = context['type']
    if backup_type not in ['monthly', 'weekly', 'daily']:
        source.reply('§c无效的备份类型，可选值：monthly(每月), weekly(每周), daily(每天)§r')
        return

    config.auto_backup_date_type = backup_type
    config.auto_backup_mode = 'date'  # 自动切换到日期模式
    config.save()

    # 如果自动备份已启用，重新设置定时任务
    if config.auto_backup_enabled:
        start_auto_backup(server_inst)

    # 显示友好的类型名称
    type_names = {'monthly': '每月', 'weekly': '每周', 'daily': '每天'}
    source.reply(f'§a已设置为{type_names[backup_type]}凌晨1点自动备份§r')
    # 显示当前配置
    show_backup_stats(source)


def set_compression_level(source: CommandSource, context: dict):
    """设置压缩等级"""
    level = context['level']
    if level not in ['speed', 'best']:
        source.reply('§c无效的压缩等级，可选值：speed(最快速度), best(最佳压缩比)§r')
        return

    # 更新配置
    config.compression_level = level
    config.save()

    # 显示成功消息
    level_names = {'speed': '最快速度', 'best': '最佳压缩比(LZMA)'}
    source.reply(f'§a已将压缩等级设置为{level_names[level]}§r')


def show_backup_stats(source: CommandSource):
    """显示定时备份状态"""
    # 获取下次备份时间
    next_backup_time = None
    if scheduler and scheduler.get_job("auto_backup_task"):
        next_backup_time = scheduler.get_job("auto_backup_task").next_run_time.strftime('%Y-%m-%d %H:%M:%S')

    # 构建状态信息
    status_lines = [
        f'定时备份状态: {"§a已开启§r" if config.auto_backup_enabled else "§c已关闭§r"}',
        f'备份模式: §6{config.auto_backup_mode}§r',
        f'备份路径: §e{config.backup_path}§r'
    ]

    if config.auto_backup_mode == 'interval':
        status_lines.append(f'备份间隔: §6{config.auto_backup_interval}{config.auto_backup_unit}§r')
    else:
        type_names = {'monthly': '每月', 'weekly': '每周', 'daily': '每天'}
        status_lines.append(f'备份类型: §6{type_names[config.auto_backup_date_type]}凌晨1点§r')
    
    if config.auto_backup_enabled and next_backup_time:
        status_lines.append(f'下次备份时间: §e{next_backup_time}§r')

    # 添加压缩等级信息
    level_names = {'speed': '最快速度', 'best': '最佳压缩比(LZMA)'}
    status_lines.append(f'压缩等级: §6{level_names.get(config.compression_level, "未知")}§r')
    
    # 输出信息
    for line in status_lines:
        source.reply(line)


def on_load(server: PluginServerInterface, old):
    """插件加载时调用的函数"""
    global creating_backup, config, server_inst
    server_inst = server
    if hasattr(old, 'creating_backup') and type(old.creating_backup) == type(creating_backup):
        creating_backup = old.creating_backup
    server.register_help_message(Prefix, '永久备份Reforged')
    config = server.load_config_simple(CONFIG_FILE, target_class=Configure, in_data_folder=False)
    register_command(server)

    # 显示加载字符画
    server.logger.info(PLUGIN_LOADED_ART)
    
    # 启动自动备份
    if config.auto_backup_enabled:
        # 初始化缺省值
        config_changed = False
        if not hasattr(config, "auto_backup_unit"):
            config.auto_backup_unit = "s"
            config_changed = True
        if not hasattr(config, "auto_backup_enabled"):
            config.auto_backup_enabled = False
            config_changed = True
        if not hasattr(config, "auto_backup_interval"):
            config.auto_backup_interval = 3600
            config_changed = True
        
        # 如果有任何配置被初始化，保存配置
        if config_changed:
            config.save()
            
        start_auto_backup(server)


def on_unload(server: PluginServerInterface):
    global plugin_unloaded
    plugin_unloaded = True
    # 停止自动备份
    stop_auto_backup()


def on_mcdr_stop(server: PluginServerInterface):
    if creating_backup.locked():
        server.logger.info('Waiting for up to 300s for permanent backup to complete')
        if creating_backup.acquire(timeout=300):
            creating_backup.release()


def register_command(server: PluginServerInterface):
    def get_literal_node(literal):
        lvl = config.minimum_permission_level.get(literal, 2)
        return Literal(literal).requires(lambda src: src.has_permission(lvl), lambda: '权限不足')

    server.register_command(
        Literal(Prefix).
        runs(lambda src: src.reply(HelpMessage)).
        then(
            get_literal_node('make').
            runs(lambda src: create_backup(src, {})).
            then(
                Text('cmt').
                runs(lambda src, ctx: create_backup(src, ctx))
            )
        ).
        then(
            get_literal_node('list').
            runs(lambda src: list_backup(src, {})).
            then(
                Integer('amount').
                runs(lambda src, ctx: list_backup(src, ctx, amount=ctx['amount']))
            )
        ).
        then(
            get_literal_node('listall').
            runs(lambda src: list_backup(src, {'amount': -1}))
        ).
        then(
            get_literal_node('stats').
            runs(lambda src: show_backup_stats(src))
        ).
        then(
            Literal('time').
            then(
                get_literal_node('enable').
                runs(lambda src: enable_auto_backup(src, server))
            ).
            then(
                get_literal_node('disable').
                runs(lambda src: disable_auto_backup(src, server))
            ).
            then(
                get_literal_node('interval').
                then(
                    Integer('time').
                    then(
                        Text('unit').
                        runs(lambda src, ctx: set_backup_interval(src, ctx))
                    )
                )
            ).
            then(
                get_literal_node('date').
                then(
                    Text('type').
                    runs(lambda src, ctx: set_backup_date(src, ctx))
                )
            ).
            then(
                get_literal_node('change').
                then(
                    Text('mode').
                    runs(lambda src, ctx: change_backup_mode(src, ctx))
                )
            )
        ).
        then(
            get_literal_node('ziplevel').
            then(
                Text('level').
                runs(lambda src, ctx: set_compression_level(src, ctx))
            )
        )
    )


def format_file_name(file_name):
    for c in ['/', '\\', ':', '*', '?', '"', '|', '<', '>']:
        file_name = file_name.replace(c, '')
    return file_name
