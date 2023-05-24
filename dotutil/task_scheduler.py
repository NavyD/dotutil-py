#!/usr/bin/env python3
import ctypes
import datetime
import getpass
import logging
import os
from shutil import which

import psutil

if psutil.WINDOWS:
    import pywintypes
    import win32com.client

log = logging.getLogger(__name__)


def is_admin():
    return ctypes.windll.shell32.IsUserAnAdmin() != 0


def setup_restic_backup(
    daily_start_time: datetime.datetime, logfile="C:\\Users\\navyd\\restic-backup.log"
):
    if not is_admin():
        raise Exception("No administrator privileges for configuring restic backup")

    if not (psbin := which("powershell.exe")):
        raise Exception("not found powershell")
    if not (bin := which("python.exe")):
        raise Exception("not found python for restic backup")
    if not (restic_backup_bin := which("restic-backup.py")):
        raise Exception("not found restic-backup.py")

    # 防止chezmoi模板和python双重转义: if($LASTEXITCODE -ne 0){ {exit $LASTEXITCODE} }
    s = "{exit $LASTEXITCODE}"
    args = [
        psbin,
        "-nologo",
        "-noprofile",
        "-command",
        f"{bin} {restic_backup_bin} *>>{logfile}; if($LASTEXITCODE -ne 0){s}",
    ]

    name = "restic-backup-autorun"
    desc = "auto run restic-backup"
    userid = ""
    if domain := os.environ.get("USERDOMAIN"):
        userid = f"{domain}\\"
    else:
        log.warning("not found env USERDOMAIN for userid")
    userid += getpass.getuser()

    log.info(f"creating task scheduler {name} with {args} for user {userid}")
    task_srv = win32com.client.Dispatch("Schedule.Service")
    task_srv.Connect()

    task_def = task_srv.NewTask(0)

    # Create trigger
    log.debug(f"creating daily trigger for task scheduler {name}")
    # [TriggerCollection.Create method](https://learn.microsoft.com/en-us/windows/win32/taskschd/triggercollection-create)
    trigger_daily = task_def.Triggers.Create(2)  # TASK_TRIGGER_DAILY
    # [LogonTrigger object](https://learn.microsoft.com/en-us/windows/win32/taskschd/logontrigger)
    trigger_daily.Enabled = True
    trigger_daily.StartBoundary = daily_start_time.isoformat()
    trigger_daily.DaysInterval = 1
    trigger_daily.Id = "DailyTriggerId"

    # Create action
    log.debug(f"creating exec action with args {args} for task scheduler {name}")
    # [ActionCollection.Create method](https://learn.microsoft.com/en-us/windows/win32/taskschd/actioncollection-create)
    action_exec = task_def.Actions.Create(0)  # TASK_ACTION_EXEC
    # [ExecAction object](https://learn.microsoft.com/en-us/windows/win32/taskschd/execaction)
    # action.ID = 'DO '
    action_exec.Path = args[0]
    # action.Arguments = '/c "exit"'
    action_exec.Arguments = " ".join(args[1:])

    log.debug("configuring task settings")
    # Set parameters
    task_def.RegistrationInfo.Description = desc
    # [TaskSettings object](https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings)
    task_def.Settings.Enabled = True
    task_def.Settings.StopIfGoingOnBatteries = False
    task_def.Settings.RunOnlyIfNetworkAvailable = True
    # start the task at any time after its scheduled time has passed
    task_def.Settings.StartWhenAvailable = True
    task_def.Settings.DisallowStartIfOnBatteries = False  # default true

    # The logon method is not specified. Used for non-NT credentials.
    # Create the principal for the task
    # [TaskDefinition.Principal property](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskdefinition-principal)
    principal_cur = task_def.Principal
    principal_cur.Id = "Principal1"
    principal_cur.UserId = userid
    #     principal_cur.UserId = 'NT AUTHORITY\\LOCALSERVICE'  # run whether user is logged on or not. require UAC
    # https://learn.microsoft.com/en-us/windows/win32/taskschd/principal-logontype#property-value
    # principal_cur.LogonType = 5  # TASK_LOGON_INTERACTIVE_TOKEN. require UAC 没找到与3的区别
    principal_cur.LogonType = 2  # TASK_LOGON_INTERACTIVE_TOKEN
    # https://learn.microsoft.com/en-us/windows/win32/taskschd/principal-runlevel
    principal_cur.RunLevel = 1  # TASK_RUNLEVEL_HIGHEST. require UAC

    # get or create folder of task
    root_folder = task_srv.GetFolder("\\")
    subfolder = "\\Restic"
    try:
        tasks_folder = root_folder.GetFolder(subfolder)
    except pywintypes.com_error:
        tasks_folder = root_folder.CreateFolder(subfolder)

    log.debug(f"registering or updating scheduler task {name} to folder {tasks_folder}")
    try:
        # [TaskFolder.RegisterTaskDefinition method](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskfolder-registertaskdefinition)
        tasks_folder.RegisterTaskDefinition(
            name,  # 任务名称
            # definition
            task_def,
            # flags A TASK_CREATION constant.
            0x6,  # TASK_CREATE_OR_UPDATE,
            # userId
            "",
            # userid,
            # password
            "",
            # logonType
            2,  # TASK_LOGON_INTERACTIVE_TOKEN
        )
        # .Run('')  # 运行任务 [RegisteredTask.Run method](https://learn.microsoft.com/en-us/windows/win32/taskschd/registeredtask-run)
    except pywintypes.com_error as e:
        # pywintypes.com_error: (-2147352571, '类型不匹配。', None, 1)
        log.error(f"failed to create task with def {task_def.__dict__} {e}")
        raise


def setup_taskscheduler_syncthing(elevated=False):
    """
    [syncthing Run at user log on or at system startup using Task Scheduler](https://docs.syncthing.net/users/autostart.html#run-at-user-log-on-or-at-system-startup-using-task-scheduler)
    """
    if not (bin := which("syncthing.exe")):
        raise Exception("not found syncthing bin")

    args = [bin, "--no-console", "--no-browser"]
    name = "syncthing-autorun-logon"
    desc = "auto run syncthing on login"
    userid = ""
    if domain := os.environ.get("USERDOMAIN"):
        userid = f"{domain}\\"
    else:
        log.warning("not found env USERDOMAIN for userid")
    userid += getpass.getuser()

    log.info(f"creating task scheduler {name} with {args} for user {userid}")
    task_srv = win32com.client.Dispatch("Schedule.Service")
    task_srv.Connect()

    task_def = task_srv.NewTask(0)

    # Create trigger
    log.debug(f"creating logon trigger for task scheduler {name}")
    # [TriggerCollection.Create method](https://learn.microsoft.com/en-us/windows/win32/taskschd/triggercollection-create)
    trigger_logon = task_def.Triggers.Create(9)  # TASK_TRIGGER_LOGON
    # [LogonTrigger object](https://learn.microsoft.com/en-us/windows/win32/taskschd/logontrigger)
    trigger_logon.Enabled = True
    trigger_logon.Delay = "PT3S"
    trigger_logon.Id = "LogonTriggerId"
    trigger_logon.UserId = userid

    # Create action
    log.debug(f"creating exec action with args {args} for task scheduler {name}")
    # [ActionCollection.Create method](https://learn.microsoft.com/en-us/windows/win32/taskschd/actioncollection-create)
    action_exec = task_def.Actions.Create(0)  # TASK_ACTION_EXEC
    # [ExecAction object](https://learn.microsoft.com/en-us/windows/win32/taskschd/execaction)
    # action.ID = 'DO '
    action_exec.Path = args[0]
    # action.Arguments = '/c "exit"'
    action_exec.Arguments = " ".join(args[1:])

    log.debug("configuring task settings")
    # Set parameters
    task_def.RegistrationInfo.Description = desc
    # [TaskSettings object](https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings)
    task_def.Settings.Enabled = True
    task_def.Settings.StopIfGoingOnBatteries = False
    task_def.Settings.DisallowStartIfOnBatteries = False  # default true

    # The logon method is not specified. Used for non-NT credentials.
    # Create the principal for the task
    # [TaskDefinition.Principal property](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskdefinition-principal)
    principal_cur = task_def.Principal
    principal_cur.Id = "Principal1"
    principal_cur.UserId = userid
    if elevated:
        log.info("use system to run whether user is logged on or not")
        principal_cur.UserId = (
            "system"  # run whether user is logged on or not. require UAC
        )
    # https://learn.microsoft.com/en-us/windows/win32/taskschd/principal-logontype#property-value
    # task_logon_interactive_token
    # principal_cur.LogonType = 5  # TASK_LOGON_INTERACTIVE_TOKEN. require UAC 没找到与3的区别
    principal_cur.LogonType = 3  # TASK_LOGON_INTERACTIVE_TOKEN
    # https://learn.microsoft.com/en-us/windows/win32/taskschd/principal-runlevel
    principal_cur.RunLevel = 0  # TASK_RUNLEVEL_LUA
    if elevated:
        log.info("run task with the highest privileges")
        principal_cur.RunLevel = 1  # TASK_RUNLEVEL_HIGHEST. require UAC

    # get or create folder of task
    root_folder = task_srv.GetFolder("\\")
    subfolder = "\\Syncthing"
    try:
        tasks_folder = root_folder.GetFolder(subfolder)
    except pywintypes.com_error:
        tasks_folder = root_folder.CreateFolder(subfolder)

    log.debug(f"registering or updating scheduler task {name} to folder {tasks_folder}")
    try:
        # [TaskFolder.RegisterTaskDefinition method](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskfolder-registertaskdefinition)
        tasks_folder.RegisterTaskDefinition(
            name,  # 任务名称
            # definition
            task_def,
            # flags A TASK_CREATION constant.
            0x6,  # TASK_CREATE_OR_UPDATE,
            # userId
            "",
            # password
            "",  # 不要使用'' No password
            # logonType
            3,  # TASK_LOGON_INTERACTIVE_TOKEN
        )
        # .Run('')  # 运行任务 [RegisteredTask.Run method](https://learn.microsoft.com/en-us/windows/win32/taskschd/registeredtask-run)
    except pywintypes.com_error as e:
        # pywintypes.com_error: (-2147352571, '类型不匹配。', None, 1)
        log.error(f"failed to create task with def {task_def.__dict__} {e}")
        raise
