
import asyncio
import salobj
import SALPY_Scheduler

loop = asyncio.get_event_loop()

remote = salobj.Remote(SALPY_Scheduler)

# Enter control

enter_t = remote.cmd_enterControl.DataType()

enter_task = loop.run_until_complete(remote.cmd_enterControl.start(enter_t))

print('Enter Control: ', enter_task.ack.ack)

# Start

settings_coro = remote.evt_settingsApplied.next()

start_t = remote.cmd_start.DataType()
start_t.settingsToApply = 'master'

start_task = loop.run_until_complete(remote.cmd_start.start(start_t))

print('Start: ', start_task.ack.ack)


settings_applied = loop.run_until_complete(settings_coro)

print('version: ', settings_applied.version)
print('scheduler: ', settings_applied.scheduler)
print('observatoryModel: ', settings_applied.observatoryModel)
print('observatoryLocation: ', settings_applied.observatoryLocation)
print('seeingModel: ', settings_applied.seeingModel)
print('cloudModel: ', settings_applied.cloudModel)
print('skybrightnessModel: ', settings_applied.skybrightnessModel)
print('downtimeModel: ', settings_applied.downtimeModel)

# Standby

standby_task = loop.run_until_complete(remote.cmd_standby.start(remote.cmd_standby.DataType()))

print('Exit: ', standby_task.ack.ack)

# Exit control

exit_task = loop.run_until_complete(remote.cmd_exitControl.start(remote.cmd_exitControl.DataType()))

print('Exit: ', exit_task.ack.ack)
