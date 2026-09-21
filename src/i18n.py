"""Small source-string localization layer for the desktop GUI.

The current English UI text is the catalog key and fallback.  Keeping the
source sentence as the key makes wording changes visible in code and prevents
localization from silently replacing the author's exact English copy.
"""
import ctypes
import locale
import re


ZH_CN = {
    'Steam Controller Calibration': 'Steam Controller 校准工具',
    'Connecting…': '正在连接…',
    'Left stick - live output': '左摇杆 - 实时输出值',
    'Right stick - live output': '右摇杆 - 实时输出值',
    'Raw calibration values': '原始校准值',
    'Axis': '轴',
    'Minimum': '最小值',
    'Center min': '中心下限',
    'Center max': '中心上限',
    'Maximum': '最大值',
    'Left X': '左 X',
    'Left Y': '左 Y',
    'Right X': '右 X',
    'Right Y': '右 Y',
    'Read Controller': '读取手柄',
    'Apply Temporarily': '临时应用',
    'Save to Controller': '保存到手柄',
    'Restore Backup…': '恢复备份…',
    'Automatic Calibration…': '自动校准…',
    'Starting controller backend…': '正在启动手柄后端…',
    'Temporary values affect the running controller but are not saved. Power-cycling discards them. A backup is created on connection.':
        '临时值会影响当前运行的手柄，但不会保存。重启手柄即可丢弃这些值。连接时会自动创建备份。',
    'Invalid calibration': '校准值无效',
    'Save calibration': '保存校准',
    'Persist the currently staged values to the controller?': '是否将当前暂存的值永久保存到手柄？',
    'Select calibration backup': '选择校准备份',
    'JSON backups': 'JSON 备份',
    'All files': '所有文件',
    'Restore calibration': '恢复校准',
    'Stage, persist, and verify both records from this backup?': '是否暂存、永久保存并验证此备份中的两条记录？',
    'Automatic calibration': '自动校准',
    'KEEP BOTH STICKS UNTOUCHED after pressing OK.\n\nThere are two five-second center measurements.\nDo not move either stick until the instruction says\nROTATE BOTH STICKS NOW.':
        '按下“确定”后，请勿触碰两个摇杆。\n\n将进行两次五秒的中心测量。\n在指示显示\n“立即转动两个摇杆”之前，请勿移动任何摇杆。',
    'Connected: {name} · {serial} · firmware {firmware}': '已连接：{name} · {serial} · 固件 {firmware}',
    'Startup backup: {path}': '启动备份：{path}',
    'Ready.': '就绪。',
    'Not connected': '未连接',
    'Calibration records read from controller.': '已从手柄读取校准记录。',
    'Values are active temporarily. Test the sticks, then save to controller. Power-cycle to revert any changes.':
        '这些值已临时生效。请测试摇杆，然后保存到手柄。重启手柄可撤销所有更改。',
    'Calibration saved and verified.': '校准已保存并验证。',
    'Backup restored and verified: {path}': '备份已恢复并验证：{path}',
    'REMOVE BOTH THUMBS FROM THE STICKS — then confirm whether to save.': '将两个拇指移开摇杆 — 然后确认是否保存。',
    'Commit automatic calibration': '提交自动校准',
    'Full travel was observed on all axes.\n\nREMOVE BOTH THUMBS FROM THE STICKS,\nthen choose Yes to persist and validate the new calibration.':
        '已在所有轴上检测到完整行程。\n\n请将两个拇指移开摇杆，\n然后选择“是”以永久保存并验证新校准。',
    'Automatic calibration saved and validated: {path}': '自动校准已保存并验证：{path}',
    'Operation in progress': '操作正在进行',
    'Wait for the current controller operation to finish before closing.': '请等待当前手柄操作完成后再关闭。',
    'Temporary calibration active': '临时校准已生效',
    'Temporary values remain active until the controller is power-cycled. Close anyway?':
        '临时值会保持生效，直到手柄重启。仍要关闭吗？',
    'Output  X {x:6d}   Y {y:6d}': '输出    X {x:6d}   Y {y:6d}',
    'Raw est X {raw_x:>6}   Y {raw_y:>6}': '原始估算 X {raw_x:>6}   Y {raw_y:>6}',
    'Recent output samples - 5 seconds': '最近的输出样本 - 5 秒',
    'Axis:': '轴：',
    'Scale:': '刻度：',
    'Logarithmic': '对数',
    'Linear': '线性',
    'A good calibration should oscillate roughly symmetrically near zero.': '良好的校准应在零点附近大致对称地波动。',
    'now {now:6d}   min {minimum:6d}   max {maximum:6d}': '当前 {now:6d}   最小 {minimum:6d}   最大 {maximum:6d}',
    'waiting for samples': '正在等待样本',
    'now': '现在',
    '−5 s': '−5 秒',
    'No Steam Controller detected. Connect to its USB port directly. DO NOT use the wireless puck.':
        '未检测到 Steam 手柄。请直接连接其 USB 端口。请勿使用无线接收器。',
    'Connect one direct-USB Steam Controller. Retrying every 2 seconds…': '请直接通过 USB 连接一个 Steam 手柄。每 2 秒重试一次…',
    'Controller is not ready ({message}). Retrying every 2 seconds…': '手柄尚未就绪（{message}）。每 2 秒重试一次…',
    'Controller disconnected. Waiting for a controller…': '手柄已断开。正在等待手柄…',
    'Backend stopped: {error}': '后端已停止：{error}',
    'A different controller appeared during the operation': '操作期间连接了另一个手柄',
    'connected controller firmware is not supported': '不支持已连接手柄的固件',
    'Reading stick reports: {error}': '读取摇杆报告时出错：{error}',
    'Reading stick-touch state: {error}': '读取摇杆触摸状态时出错：{error}',
    'Both stick-touch sensors must report released before calibration can be saved': '保存校准前，两个摇杆触摸传感器都必须报告已松开',
    'Reading post-commit stick-touch state: {error}': '读取提交后的摇杆触摸状态时出错：{error}',
    'Automatic calibration cancelled; nothing was persisted.': '自动校准已取消；未永久保存任何内容。',
    'Staging edited records temporarily…': '正在临时暂存编辑后的记录…',
    'Temporary record readback did not match the edits': '临时记录的读回值与编辑值不符',
    'Apply values temporarily before saving them': '保存前请先临时应用这些值',
    'Saving staged records to the controller…': '正在将暂存记录保存到手柄…',
    'Persistent record readback did not match the staged values': '永久记录的读回值与暂存值不符',
    'Backup belongs to another controller': '备份属于另一个手柄',
    'KEEP BOTH STICKS COMPLETELY UNTOUCHED — checking center for 5 seconds.': '请完全不要触碰两个摇杆 — 正在检查中心位置，持续 5 秒。',
    'Center preflight failed; no calibration phase was sent': '中心预检失败；未发送任何校准阶段命令',
    'KEEP BOTH STICKS COMPLETELY UNTOUCHED — collecting center for 5 seconds.': '请完全不要触碰两个摇杆 — 正在采集中心位置，持续 5 秒。',
    'ROTATE BOTH STICKS NOW — use their full circular travel for 12 seconds.': '立即转动两个摇杆 — 在 12 秒内沿完整圆周范围转动。',
    'Full travel was not observed on every axis; nothing was persisted': '未在每个轴上检测到完整行程；未永久保存任何内容',
    'No automatic calibration is waiting to commit': '没有等待提交的自动校准',
    'REMOVE BOTH THUMBS FROM THE STICKS — waiting for both touch sensors to release.': '将两个拇指移开摇杆 — 正在等待两个触摸传感器松开。',
    'Stick touch did not release; automatic calibration was cancelled and not saved': '摇杆触摸状态未松开；自动校准已取消且未保存',
    'Committing and validating automatic calibration…': '正在提交并验证自动校准…',
    'Unsafe calibration was automatically rolled back': '不安全的校准已自动回滚',
    'Unsafe calibration and automatic rollback failed; restore the backup': '校准不安全且自动回滚失败；请恢复备份',
    'Calibration record fields must be integers': '校准记录字段必须是整数',
    'Calibration values must fit unsigned 16-bit storage': '校准值必须在无符号 16 位存储范围内',
    'Each axis must satisfy min < center_min <= center_max < max': '每个轴必须满足：最小值 < 中心下限 <= 中心上限 < 最大值',
    'calibration bounds are not ordered': '校准边界顺序不正确',
    'File is not a supported immutable stick backup': '该文件不是受支持的不可变摇杆备份',
    'Backup identity or firmware build is unsupported': '不支持此备份的设备身份或固件版本',
    'Backup fingerprint does not match its device identity and records': '备份指纹与其设备身份和记录不符',
    'Path is not a currently enumerated 2026 Valve device; run list again': '该路径不是当前枚举到的 2026 Valve 设备；请重新运行设备列表',
}


_language = 'en'


def _normalize(language):
    """Collapse locale spellings to one of the two catalogs we provide."""
    value = (language or '').replace('_', '-').lower()
    return 'zh-CN' if value.startswith('zh') else 'en'


def detect_system_language():
    """Read the Windows UI language, with locale-based fallbacks."""
    try:
        # LANGIDs use 0x04 for the primary Chinese language across regions.
        if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3ff == 0x04:
            return 'zh-CN'
        buffer = ctypes.create_unicode_buffer(85)
        if ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, len(buffer)):
            return _normalize(buffer.value)
    except (AttributeError, OSError):
        pass
    try:
        return _normalize(locale.getlocale()[0])
    except (TypeError, ValueError):
        return 'en'


def configure(language='auto'):
    """Select a catalog and return the resolved language name."""
    global _language
    _language = detect_system_language() if language == 'auto' else _normalize(language)
    return _language


def current_language():
    return _language


def ui_font(size, weight=None):
    """Return the Windows UI font appropriate for the active language."""
    family = 'Microsoft YaHei UI' if _language == 'zh-CN' else 'Segoe UI'
    return (family, size, weight) if weight else (family, size)


def tr(source, **values):
    """Translate a canonical English source string and interpolate named values."""
    translated = ZH_CN.get(source, source) if _language == 'zh-CN' else source
    return translated.format(**values) if values else translated


def tr_error(message):
    """Translate validation errors that cross from protocol code into the GUI."""
    if _language != 'zh-CN':
        return message
    if message in ZH_CN:
        return ZH_CN[message]
    patterns = (
        (r'^(x|y) travel span (\d+) is below 1500$', r'\1 轴行程范围 \2 小于 1500'),
        (r'^(x|y) center width (\d+) exceeds 10% of travel$', r'\1 轴中心宽度 \2 超过行程的 10%'),
        (r'^(x|y) center window is too close to a travel limit$', r'\1 轴中心窗口过于接近行程边界'),
    )
    for pattern, replacement in patterns:
        if re.match(pattern, message):
            return re.sub(pattern, replacement, message)
    # Preserve record names while translating the validation text after them.
    if ': ' in message:
        prefix, detail = message.split(': ', 1)
        translated = tr_error(detail)
        if translated != detail:
            return f'{prefix}: {translated}'
    return message
