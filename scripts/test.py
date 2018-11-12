#!/usr/bin/env python
__all__ = ["MyTestScript"]

import asyncio

import salobj
from ts_scriptqueue.base_script import BaseScript
import SALPY_Test


class MyTestScript(BaseScript):
    """Test script to allow testing BaseScript.

    Parameters
    ----------
    index : `int`
        Index of Script SAL component.

    Wait for the specified time, then exit. See `configure` for details.
    """
    __test__ = False  # stop pytest from warning that this is not a test

    def __init__(self, index, descr=""):
        super().__init__(index=index, descr=descr,
                         remotes_dict={'test': salobj.Remote(SALPY_Test, 1)})

        self.up = True
        self.wait_time = 0
        self.fail_run = False
        self.fail_cleanup = False

    async def configure(self, up=True, wait_time=0, fail_run=False, fail_cleanup=False):
        """Configure the script.

        Parameters
        ----------
        up : `bool`
            Bring component up? Default is `True`.
        wait_time : `float`
            Time to wait, in seconds
        fail_run : `bool`
            If True then raise an exception in `run` after the "start"
            checkpoint but before waiting.
        fail_cleanup : `bool`
            If True then raise an exception in `cleanup`.

        Raises
        ------
        salobj.ExpectedError
            If ``wait_time < 0``. This can be used to make config fail.
        """
        self.log.info("Configure started")
        self.up = up
        self.wait_time = float(wait_time)
        if self.wait_time < 0:
            raise salobj.ExpectedError(f"wait_time={self.wait_time} must be >= 0")
        self.fail_run = bool(fail_run)
        self.fail_cleanup = bool(fail_cleanup)

        self.log.info(f"up={self.up}, "
                      f"wait_time={self.wait_time}, "
                      f"fail_run={self.fail_run}, "
                      f"fail_cleanup={self.fail_cleanup}, "
                      )
        self.log.info("Configure succeeded")

    def set_metadata(self, metadata):
        metadata.duration = self.wait_time

    async def run(self):
        self.log.info("Run started")
        await self.checkpoint("start")

        print(self.fail_run)
        if self.fail_run:
            raise salobj.ExpectedError(f"Failed in run after wait: fail_run={self.fail_run}")

        if self.up:
            await self.bring_up()
        else:
            await self.bring_down()

        await asyncio.sleep(self.wait_time)

        await self.checkpoint("end")
        self.log.info("Run succeeded")

    async def cleanup(self):
        self.log.info("Cleanup started")
        if self.fail_cleanup:
            raise salobj.ExpectedError(f"Failed in cleanup: fail_cleanup={self.fail_cleanup}")
        self.log.info("Cleanup succeeded")

    async def bring_up(self):
        """Bring component up from STANDBY to ENABLE

        Returns
        -------

        """
        summary_state_coro = self.test.evt_summaryState.next(timeout=2.)

        # STANDBY -> DISABLE
        await self.checkpoint("cmd_start")

        # If this timeout, just gives up
        start_task = await self.test.cmd_start.start(self.test.cmd_start.DataType(), timeout=10.)

        # It may fail, but will still proceed
        self.log.debug("ack: %i %i %s", start_task.ack.ack, start_task.ack.error, start_task.ack.result)

        # If it fails to send start command, we will probably not get summary state and this will timeout
        try:
            test_state = await summary_state_coro
        except asyncio.TimeoutError:
            self.log.error('Could not get summary state.')
        else:
            self.log.info('Test component in %s state', test_state.summaryState)

        self.log.debug('Sleeping for %f seconds.', self.wait_time)
        await asyncio.sleep(self.wait_time)

        # DISABLE -> ENABLE
        await self.checkpoint("cmd_enable")

        summary_state_coro = self.test.evt_summaryState.next(timeout=2.)

        # If this timeout, just gives up
        enable_task = await self.test.cmd_enable.start(self.test.cmd_enable.DataType(), timeout=10.)

        # It may fail, but will still proceed
        self.log.debug("ack: %i %i %s", enable_task.ack.ack, enable_task.ack.error, enable_task.ack.result)

        # If it fails to send start command, we will probably not get summary state and this will timeout
        try:
            test_state = await summary_state_coro
        except asyncio.TimeoutError:
            self.log.error('Could not get summary state.')
        else:
            self.log.info('Test component in %s state', test_state.summaryState)

    async def bring_down(self):
        """Bring component up from ENABLE to STANDBY

        Returns
        -------

        """
        summary_state_coro = self.test.evt_summaryState.next(timeout=2.)

        # ENABLE -> DISABLE
        await self.checkpoint("cmd_disable")

        # If this timeout, just gives up
        disable_task = await self.test.cmd_disable.start(self.test.cmd_disable.DataType(), timeout=10.)

        # It may fail, but will still proceed
        self.log.debug("ack: %i %i %s", disable_task.ack.ack, disable_task.ack.error, disable_task.ack.result)

        # If it fails to send start command, we will probably not get summary state and this will timeout
        try:
            test_state = await summary_state_coro
        except asyncio.TimeoutError:
            self.log.error('Could not get summary state.')
        else:
            self.log.info('Test component in %s state', test_state.summaryState)

        self.log.debug('Sleeping for %f seconds.', self.wait_time)
        await asyncio.sleep(self.wait_time)

        # DISABLE -> STANDBY
        await self.checkpoint("cmd_standby")

        summary_state_coro = self.test.evt_summaryState.next(timeout=2.)

        # If this timeout, just gives up
        standby_task = await self.test.cmd_standby.start(self.test.cmd_standby.DataType(), timeout=10.)

        # It may fail, but will still proceed
        self.log.debug("ack: %i %i %s", standby_task.ack.ack, standby_task.ack.error, standby_task.ack.result)

        # If it fails to send start command, we will probably not get summary state and this will timeout
        try:
            test_state = await summary_state_coro
        except asyncio.TimeoutError:
            self.log.error('Could not get summary state.')
        else:
            self.log.info('Test component in %s state', test_state.summaryState)


if __name__ == "__main__":
    MyTestScript.main(descr="external test.py")
