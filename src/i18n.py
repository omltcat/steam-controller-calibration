"""Central English and Simplified-Chinese catalogs for the desktop GUI.

Callers use stable message IDs such as ``tr('button.read_controller')``.
Visible wording lives only in this file, so copy can be revised or translated
without searching through the controller and Tk presentation code.
"""
import ctypes
import locale
import re


REPOSITORY_URL = 'https://github.com/omltcat/steam-controller-calibration'
ISSUES_URL = f'{REPOSITORY_URL}/issues'


EN = {
    'app.title': 'Steam Controller Calibration',
    'connection.connecting': 'Connecting…',
    'connection.connected': 'Connected: {name} · {serial} · firmware {firmware} ({support})',
    'connection.not_connected': 'Not connected',
    'connection.no_controller': 'No Steam Controller detected. Connect to its USB port directly. DO NOT use the wireless puck.',
    'connection.one_controller': 'Connect one direct-USB Steam Controller. Retrying every 2 seconds…',
    'connection.not_ready': 'Controller is not ready ({message}). Retrying every 2 seconds…',
    'connection.disconnected': 'Controller disconnected. Waiting for a controller…',
    'connection.different_controller': 'A different controller appeared during the operation',
    'connection.unsupported_firmware': 'connected controller firmware is not supported',
    'support.hardware_tested': 'supported',
    'support.reviewed': 'untested',
    'support.unknown': 'unknown',
    'stick.left_title': 'Left stick - live output',
    'stick.right_title': 'Right stick - live output',
    'stick.output': 'Output  X {x:6d}   Y {y:6d}',
    'stick.raw_estimate': 'Raw est X {raw_x:>6}   Y {raw_y:>6}',
    'editor.title': 'Raw calibration values',
    'editor.axis': 'Axis',
    'editor.minimum': 'Minimum',
    'editor.center_min': 'Center min',
    'editor.center_max': 'Center max',
    'editor.maximum': 'Maximum',
    'axis.left_x': 'Left X',
    'axis.left_y': 'Left Y',
    'axis.right_x': 'Right X',
    'axis.right_y': 'Right Y',
    'button.read': 'Read Controller',
    'button.stage': 'Apply Temporarily',
    'button.save': 'Save to Controller',
    'button.restore': 'Restore Backup…',
    'button.auto': 'Automatic Calibration…',
    'plot.title': 'Recent output samples - 5 seconds',
    'plot.axis': 'Axis:',
    'plot.scale': 'Scale:',
    'plot.logarithmic': 'Logarithmic',
    'plot.linear': 'Linear',
    'plot.guidance': 'A good calibration should oscillate roughly symmetrically near zero.',
    'plot.summary': 'now {now:6d}   min {minimum:6d}   max {maximum:6d}',
    'plot.waiting': 'waiting for samples',
    'status.starting': 'Starting controller backend…',
    'status.ready': 'Ready.',
    'status.backup_path': 'Startup backup: {path}',
    'status.records_read': 'Calibration records read from controller.',
    'status.staged': 'Values are active temporarily. Test the sticks, then save to controller. Power-cycle to revert any changes.',
    'status.saved': 'Calibration saved and verified.',
    'status.restored': 'Backup restored and verified: {path}',
    'status.auto_ready': 'REMOVE BOTH THUMBS FROM THE STICKS — then confirm whether to save.',
    'status.auto_saved': 'Automatic calibration saved and validated: {path}',
    'status.writes_enabled': 'Write operations enabled for {support} firmware {firmware}.',
    'status.writes_disabled': 'Write operations are disabled for this firmware. Live monitoring remains available.',
    'status.temporary_explanation': 'Temporary values affect the running controller but are not saved. Power-cycling discards them. A backup is created on connection.',
    'footer.problem': 'For problems and unsupported firmware:',
    'footer.issues_link': 'submit an issue.',
    'footer.star': 'If this app helps you, please',
    'footer.repository_link': 'leave a star on GitHub.',
    'footer.author': 'Made by omltcat',
    'footer.author_link': 'https://github.com/omltcat',
    'footer.license': 'under AGPLv3 license.',
    'status.auto_cancelled': 'Automatic calibration cancelled; nothing was persisted.',
    'status.staging': 'Staging edited records temporarily…',
    'status.saving': 'Saving staged records to the controller…',
    'status.center_check': 'KEEP BOTH STICKS COMPLETELY UNTOUCHED — checking center for 5 seconds.',
    'status.center_collect': 'KEEP BOTH STICKS COMPLETELY UNTOUCHED — collecting center for 5 seconds.',
    'status.rotate': 'ROTATE BOTH STICKS NOW — use their full circular travel for 12 seconds.',
    'status.wait_touch_release': 'REMOVE BOTH THUMBS FROM THE STICKS — waiting for both touch sensors to release.',
    'status.committing_auto': 'Committing and validating automatic calibration…',
    'dialog.invalid_calibration': 'Invalid calibration',
    'dialog.invalid_backup': 'Invalid calibration backup',
    'dialog.save_calibration': 'Save calibration',
    'dialog.restore_calibration': 'Restore calibration',
    'dialog.cross_firmware_restore': 'Cross-firmware restore',
    'dialog.auto_calibration': 'Automatic calibration',
    'dialog.commit_auto': 'Commit automatic calibration',
    'dialog.reviewed_firmware': 'Reviewed firmware',
    'dialog.unknown_firmware': 'Unknown firmware',
    'dialog.operation_in_progress': 'Operation in progress',
    'dialog.temporary_active': 'Temporary calibration active',
    'dialog.select_backup': 'Select calibration backup',
    'filetype.json': 'JSON backups',
    'filetype.all': 'All files',
    'prompt.persist_staged': 'Persist the currently staged values to the controller?',
    'prompt.restore': 'Stage, persist, and verify both records from this backup?',
    'prompt.cross_firmware_invalid': 'This backup cannot be used across firmware versions because its calibration values failed strict checks:\n\n{issues}',
    'prompt.cross_firmware': 'This backup was created by firmware {backup_firmware}, but the connected controller uses firmware {current_firmware}.\n\nThe backup fingerprint and calibration values are valid, but firmware may interpret them differently. Restoring across firmware versions is discouraged and rollback is not guaranteed.\n\nContinue only if you understand the risk.',
    'prompt.auto_start': 'KEEP BOTH STICKS UNTOUCHED after pressing OK.\n\nThere are two five-second center measurements.\nDo not move either stick until the instruction says\nROTATE BOTH STICKS NOW.',
    'prompt.auto_commit': 'Full travel was observed on all axes.\n\nREMOVE BOTH THUMBS FROM THE STICKS,\nthen choose Yes to persist and validate the new calibration.',
    'prompt.reviewed_firmware': 'Firmware {firmware} has been reviewed against the calibration protocol, but has not been tested on hardware.\n\nCalibration and rollback may fail or behave unexpectedly.\n\nYou can help contribute to this project by testing and providing feedback on this firmware via GitHub Issues.\n\nContinue and enable write operations for this controller session?',
    'prompt.unknown_firmware': 'Firmware {firmware} has not been reviewed or tested.\n\nCalibration and rollback may fail or behave unexpectedly.\n\nYou can help contribute to this project by reporting this firmware version via GitHub Issues.\n\nDo you understand the risks and still want to enable write operations for this controller session?',
    'prompt.close_busy': 'Wait for the current controller operation to finish before closing.',
    'prompt.close_staged': 'Temporary values remain active until the controller is power-cycled. Close anyway?',
    'error.backend_stopped': 'Backend stopped: {error}',
    'error.read_sticks': 'Reading stick reports: {error}',
    'error.read_touch': 'Reading stick-touch state: {error}',
    'error.read_post_commit_touch': 'Reading post-commit stick-touch state: {error}',
    'error.touch_release_required': 'Both stick-touch sensors must report released before calibration can be saved',
    'error.center_preflight': 'Center preflight failed; no calibration phase was sent',
    'error.full_travel': 'Full travel was not observed on every axis; nothing was persisted',
    'error.no_auto_pending': 'No automatic calibration is waiting to commit',
    'error.touch_not_released': 'Stick touch did not release; automatic calibration was cancelled and not saved',
    'error.temporary_readback': 'Temporary record readback did not match the edits',
    'error.persisted_readback': 'Persistent record readback did not match the staged values',
    'error.stage_before_save': 'Apply values temporarily before saving them',
    'error.other_controller_backup': 'Backup belongs to another controller',
    'error.auto_rolled_back': 'Unsafe calibration was automatically rolled back',
    'error.auto_rollback_failed': 'Unsafe calibration and automatic rollback failed; restore the backup',
    'protocol.record_fields_integer': 'Calibration record fields must be integers',
    'protocol.uint16_values': 'Calibration values must fit unsigned 16-bit storage',
    'protocol.bounds_order': 'Each axis must satisfy min < center_min <= center_max < max',
    'protocol.bounds_not_ordered': 'calibration bounds are not ordered',
    'protocol.invalid_backup': 'File is not a supported immutable stick backup',
    'protocol.unsupported_backup_identity': 'Backup identity or firmware build is unsupported',
    'protocol.invalid_backup_fingerprint': 'Backup fingerprint does not match its device identity and records',
    'protocol.invalid_hid_path': 'Path is not a currently enumerated 2026 Valve device; run list again',
}

ZH_CN = {
    'app.title': 'Steam Controller 校准工具',
    'connection.connecting': '正在连接…',
    'connection.connected': '已连接：{name} · {serial} · 固件 {firmware}（{support}）',
    'connection.not_connected': '未连接',
    'connection.no_controller': '未检测到 Steam 手柄。请直接连接其 USB 端口。请勿使用无线接收器。',
    'connection.one_controller': '请直接通过 USB 连接一个 Steam 手柄。每 2 秒重试一次…',
    'connection.not_ready': '手柄尚未就绪（{message}）。每 2 秒重试一次…',
    'connection.disconnected': '手柄已断开。正在等待手柄…',
    'connection.different_controller': '操作期间连接了另一个手柄',
    'connection.unsupported_firmware': '不支持已连接手柄的固件',
    'support.hardware_tested': '已支持',
    'support.reviewed': '未测试',
    'support.unknown': '未知',
    'stick.left_title': '左摇杆 - 实时输出值',
    'stick.right_title': '右摇杆 - 实时输出值',
    'stick.output': '输出    X {x:6d}   Y {y:6d}',
    'stick.raw_estimate': '原始估算 X {raw_x:>6}   Y {raw_y:>6}',
    'editor.title': '原始校准值',
    'editor.axis': '轴',
    'editor.minimum': '最小值',
    'editor.center_min': '中心下限',
    'editor.center_max': '中心上限',
    'editor.maximum': '最大值',
    'axis.left_x': '左 X',
    'axis.left_y': '左 Y',
    'axis.right_x': '右 X',
    'axis.right_y': '右 Y',
    'button.read': '读取手柄',
    'button.stage': '临时应用',
    'button.save': '保存到手柄',
    'button.restore': '恢复备份…',
    'button.auto': '自动校准…',
    'plot.title': '最近的输出样本 - 5 秒',
    'plot.axis': '轴：',
    'plot.scale': '刻度：',
    'plot.logarithmic':'对数',
    'plot.linear': '线性',
    'plot.guidance': '良好的校准应在零点附近大致对称地波动。',
    'plot.summary': '当前 {now:6d}   最小 {minimum:6d}   最大 {maximum:6d}',
    'plot.waiting': '正在等待样本',
    'status.starting': '正在启动手柄后端…',
    'status.ready': '就绪。',
    'status.backup_path': '启动备份：{path}',
    'status.records_read': '已从手柄读取校准记录。',
    'status.staged': '这些值已临时生效。请测试摇杆，然后保存到手柄。重启手柄可撤销所有更改。',
    'status.saved': '校准已保存并验证。',
    'status.restored': '备份已恢复并验证：{path}',
    'status.auto_ready': '将两个拇指移开摇杆 — 然后确认是否保存。',
    'status.auto_saved': '自动校准已保存并验证：{path}',
    'status.writes_enabled': '已为{support}固件 {firmware} 启用写入操作。',
    'status.writes_disabled': '此固件的写入操作已禁用。仍可使用实时监控。',
    'status.temporary_explanation': '临时值会影响当前运行的手柄，但不会保存。重启手柄即可丢弃这些值。连接时会自动创建备份。',
    'footer.problem': '遇到问题或尚未支持的固件:',
    'footer.issues_link': '提交 Issues。',
    'footer.star': '如果本工具帮到了你，请在',
    'footer.repository_link': 'GitHub 仓库点个 Star。',
    'footer.author': '小猫蛋卷 制作,',
    'footer.author_link': 'https://space.bilibili.com/257463461',
    'footer.license': 'AGPLv3 开源许可。',
    'status.auto_cancelled': '自动校准已取消；未永久保存任何内容。',
    'status.staging': '正在临时暂存编辑后的记录…',
    'status.saving': '正在将暂存记录保存到手柄…',
    'status.center_check': '请完全不要触碰两个摇杆 — 正在检查中心位置，持续 5 秒。',
    'status.center_collect': '请完全不要触碰两个摇杆 — 正在采集中心位置，持续 5 秒。',
    'status.rotate': '立即转动两个摇杆 — 在 12 秒内沿完整圆周范围转动。',
    'status.wait_touch_release': '将两个拇指移开摇杆 — 正在等待两个触摸传感器松开。',
    'status.committing_auto': '正在提交并验证自动校准…',
    'dialog.invalid_calibration': '校准值无效',
    'dialog.invalid_backup': '校准备份无效',
    'dialog.save_calibration': '保存校准',
    'dialog.restore_calibration': '恢复校准',
    'dialog.cross_firmware_restore': '跨固件恢复',
    'dialog.auto_calibration': '自动校准',
    'dialog.commit_auto': '提交自动校准',
    'dialog.reviewed_firmware': '未测试的固件',
    'dialog.unknown_firmware': '未知固件',
    'dialog.operation_in_progress': '操作正在进行',
    'dialog.temporary_active': '临时校准已生效',
    'dialog.select_backup': '选择校准备份',
    'filetype.json': 'JSON 备份',
    'filetype.all': '所有文件',
    'prompt.persist_staged': '是否将当前暂存的值永久保存到手柄？',
    'prompt.restore': '是否暂存、永久保存并验证此备份中的两条记录？',
    'prompt.cross_firmware_invalid': '此备份的校准值未通过严格检查，因此不能用于跨固件版本恢复：\n\n{issues}',
    'prompt.cross_firmware': '此备份由固件 {backup_firmware} 创建，但已连接手柄使用固件 {current_firmware}。\n\n备份指纹和校准值均有效，但不同固件可能会以不同方式解释这些值。不建议跨固件版本恢复，也无法保证可以回滚。\n\n仅在了解风险的情况下继续。',
    'prompt.auto_start': '按下“确定”后，请勿触碰两个摇杆。\n\n将进行两次五秒的中心测量。\n在指示显示\n“立即转动两个摇杆”之前，请勿移动任何摇杆。',
    'prompt.auto_commit': '已在所有轴上检测到完整行程。\n\n请将两个拇指移开摇杆，\n然后选择“是”以永久保存并验证新校准。',
    'prompt.reviewed_firmware': '固件 {firmware} 已根据校准协议完成评估，但尚未经过硬件测试。\n\n校准和回滚可能失败或出现异常。\n\n你可以在本固件上测试并通过GitHub Issues提供反馈，以帮助改进本项目。\n\n是否继续并为本次手柄会话启用写入操作？',
    'prompt.unknown_firmware': '固件 {firmware} 未经过评估或测试。\n\n校准和回滚可能失败或出现异常。\n\n你可以通过GitHub Issues报告此固件版本，以帮助改进本项目。\n\n是否了解风险并仍要为本次手柄会话启用写入操作？',
    'prompt.close_busy': '请等待当前手柄操作完成后再关闭。',
    'prompt.close_staged': '临时值会保持生效，直到手柄重启。仍要关闭吗？',
    'error.backend_stopped': '后端已停止：{error}',
    'error.read_sticks': '读取摇杆报告时出错：{error}',
    'error.read_touch': '读取摇杆触摸状态时出错：{error}',
    'error.read_post_commit_touch': '读取提交后的摇杆触摸状态时出错：{error}',
    'error.touch_release_required': '保存校准前，两个摇杆触摸传感器都必须报告已松开',
    'error.center_preflight': '中心预检失败；未发送任何校准阶段命令',
    'error.full_travel': '未在每个轴上检测到完整行程；未永久保存任何内容',
    'error.no_auto_pending': '没有等待提交的自动校准',
    'error.touch_not_released': '摇杆触摸状态未松开；自动校准已取消且未保存',
    'error.temporary_readback': '临时记录的读回值与编辑值不符',
    'error.persisted_readback': '永久记录的读回值与暂存值不符',
    'error.stage_before_save': '保存前请先临时应用这些值',
    'error.other_controller_backup': '备份属于另一个手柄',
    'error.auto_rolled_back': '不安全的校准已自动回滚',
    'error.auto_rollback_failed': '校准不安全且自动回滚失败；请恢复备份',
    'protocol.record_fields_integer': '校准记录字段必须是整数',
    'protocol.uint16_values': '校准值必须在无符号 16 位存储范围内',
    'protocol.bounds_order': '每个轴必须满足：最小值 < 中心下限 <= 中心上限 < 最大值',
    'protocol.bounds_not_ordered': '校准边界顺序不正确',
    'protocol.invalid_backup': '该文件不是受支持的不可变摇杆备份',
    'protocol.unsupported_backup_identity': '不支持此备份的设备身份或固件版本',
    'protocol.invalid_backup_fingerprint': '备份指纹与其设备身份和记录不符',
    'protocol.invalid_hid_path': '该路径不是当前枚举到的 2026 Valve 设备；请重新运行设备列表',
}

CATALOGS = {
    'en': EN,
    'zh-CN': ZH_CN,
}


_language = 'en'


def _normalize(language):
    """Collapse locale spellings to one of the two catalogs we provide."""
    value = (language or '').replace('_',
    '-').lower()
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


def data_font(size):
    """Keep live numeric output and graph labels aligned in every language."""
    return ('Consolas', size)


def tr(key, **values):
    """Translate a message ID and interpolate its named placeholders."""
    try:
        translated = CATALOGS[_language][key]
    except KeyError as error:
        raise KeyError(f'Unknown localization message ID: {key}') from error
    return translated.format(**values) if values else translated


def tr_error(message):
    """Translate validation errors that cross from protocol code into the GUI."""
    if _language != 'zh-CN':
        return message
    # Protocol errors can originate outside the GUI, where translating message
    # IDs would make diagnostics less useful.  Match their English wording
    # against this catalog when a direct translation is available.
    for key, english in EN.items():
        if message == english:
            return CATALOGS['zh-CN'][key]
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
