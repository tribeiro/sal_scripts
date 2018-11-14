#!/usr/bin/env python

import os
import argparse
import logging
import pandas as pd
import sqlite3
import time
import datetime

import SALPY_MTPtg
import SALPY_MTMount

"""
This script is designed to drive a night simulation using the pointing kernel. It can perform actions like;
enable/disable the pointing kernel and load an OpSim database and send targets to the pointing kernel. When
sending targets from an OpSim database, it will listen for events from the mount to measure if the mount arrived
at the specified position. The time it takes to go from one position to another will be matched with the expected
slew time. If is is shorter the simulator will add the remaining time to the exposure time. If it is longer it will
decrease the exposure time accordingly. If the remaining time (expected slew + exposure time < actual slew) then, it
will add the difference to a buffer and send the telescope to the next target. Any time that the actual slew is shorter
then the expected slew, the buffer will be subtracted, as to try to maintain integrity of the target list. If the
buffer gets larger than a certain amount the simulation will be terminated as the integrity of the target list cannot
be guaranteed.
"""

logging.getLogger().setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG,
                format='[%(asctime)s] [%(name)-12s:%(lineno)-4d] [%(levelname)-8s]: %(message)s',
                datefmt='%m-%d %H:%M:%S')


def create_parser():
    """Create parser
    """
    description = ["This script is designed to drive a night simulation using the pointing kernel."]

    parser = argparse.ArgumentParser(usage="visit_sim_driver.py [options]",
                                     description=" ".join(description),
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-v", "--verbose", dest="verbose", action='count', default=0,
                        help="Set the verbosity for the console logging.")
    parser.add_argument("-e", '--enable', dest='enable', action='store_true',
                        help="Enable pointing kernel.")
    parser.add_argument("-d", "--disable", dest="disable", action="store_true",
                        help="Disable pointing kernel.")
    parser.add_argument('--max-buffer', dest='max_buffer', default=60., type=float,
                        help="Maximum buffer size before finalizing the simulation (in seconds).")
    parser.add_argument('--time-zone', dest='time_zone', default=-2., type=float,
                        help="Time zone difference to compute Local Sidereal Time (hours).")
    parser.add_argument('--timeout', dest='timeout', default=5, type=int,
                        help="Command timeout (in seconds).")
    parser.add_argument("--database", dest="database", default=None, type=str,
                        help="Filename with the run database.")

    return parser


def main(args):

    log = logging.getLogger(__name__)
    mgr = SALPY_MTPtg.SAL_MTPtg()
    mgr.salCommand("MTPtg_command_start")
    mgr.salCommand("MTPtg_command_enable")
    mgr.salCommand("MTPtg_command_disable")
    mgr.salCommand("MTPtg_command_standby")
    mgr.salCommand("MTPtg_command_raDecTarget")
    mgr.salTelemetrySub("MTPtg_timeAndDate")

    def disable():
        log.debug('Disabling PT Kernel...')
        disable = SALPY_MTPtg.MTPtg_command_disableC()
        cmdId = mgr.issueCommand_disable(disable)
        retval = mgr.waitForCompletion_disable(cmdId, args.timeout)
        if retval < 0:
            log.warning("Could not Disable PT Kernel. Continuing...")
        return retval

    # If pt kernel needs enabling, enable it
    if args.enable:
        log.debug('Starting PT Kernel...')
        start = SALPY_MTPtg.MTPtg_command_startC()
        cmdId = mgr.issueCommand_start(start)
        retval = mgr.waitForCompletion_start(cmdId, args.timeout)
        if retval < 0:
            raise IOError("Could not start MTPtg.")

        log.debug('Enabling PT Kernel...')
        enable = SALPY_MTPtg.MTPtg_command_enableC()
        cmdId = mgr.issueCommand_enable(enable)
        retval = mgr.waitForCompletion_enable(cmdId, args.timeout)
        if retval < 0:
            raise IOError("Could not enable MTPtg.")

    else:
        log.debug('Pointing kernel will not be enabled...')

    if args.database is None:
        raise IOError('Database must be defined. Use --database <filename.db>.')
    elif not os.path.exists(args.database):
        log.error('File %s does not exists. Specify valid database with --database option.', args.database)
        return -1

    # preparing topic to publish
    target_data = SALPY_MTPtg.MTPtg_command_raDecTargetC()
    target_data.frame = 1
    target_data.epoch = 2000.
    target_data.equinox = 2000.

    target_data.parallax = 0.
    target_data.pmRA = 0.
    target_data.pmDec = 0.
    target_data.rv = 0.
    target_data.dRA = 0.
    target_data.dDec = 0.
    target_data.rotPA = 0.
    target_data.rotFrame = 1
    target_data.rotMode = 1

    # topic for time and date from the pointing kernel
    time_data = SALPY_MTPtg.MTPtg_timeAndDateC()

    log.debug('Reading input data from %s', args.database)

    conn = sqlite3.connect(args.database)
    df = pd.read_sql_query("select * from summaryAllProps;", conn)

    log.debug('Got %i targets from database. Starting simulation', len(df))

    buffer = 0.
    try:
        for i in range(len(df)):
            ra = df['fieldRA'][i]
            dec = df['fieldDec'][i]
            observation_lst = df['observationStartLST'][i]
            slewtime = df['slewTime'][i]
            exptime = df['visitExposureTime'][i]

            ha = observation_lst - ra  # compute hour angle of the observation

            # now, I need to get the local sidereal time
            # now = datetime.datetime.now()
            retval = mgr.getNextSample_timeAndDate(time_data)

            # Read everything in the buffer...
            while retval < 0:
                retval = mgr.getNextSample_timeAndDate(time_data)

            log.debug('Current LST: %s', time_data.lst)
            hour, minute, second = time_data.lst.split(':')
            current_lst = (float(hour) + float(minute)/60. + float(second)/60./60.)

            current_ra = current_lst - ha * 24. / 360.   # in hours

            log.debug('Target[%i]: %8.2f %8.2f', i+1, current_ra, dec)

            target_data.targetName = 'target_%04i' % (i+1)
            target_data.targetInstance = i+1
            target_data.ra = '%f' % current_ra
            target_data.declination = '%f' % dec

            cmdId = mgr.issueCommand_raDecTarget(target_data)

            before_cmd_time = time.time()
            retval = mgr.waitForCompletion_raDecTarget(cmdId, args.timeout)

            if retval < 0:
                raise IOError('Command %i not ok...' % cmdId)

            cmd_time = time.time()-before_cmd_time

            log.debug('Command took %f s', cmd_time)

            # Send target
            log.debug('Slewing (%.2f s)...', slewtime)
            # TODO: loop to get signal from Mount
            time.sleep(slewtime)

            log.debug('Exposing (%.2f s)...', exptime)
            time.sleep(exptime)

            log.debug('Done')
    except Exception as e:
        disable()
        raise e

    # at the end, disable pt kernel if requested
    if args.disable:

        disable()

        log.debug('Standing by PT Kernel...')
        standby = SALPY_MTPtg.MTPtg_command_standbyC()
        cmdId = mgr.issueCommand_standby(standby)
        retval = mgr.waitForCompletion_standby(cmdId, args.timeout)
        if retval < 0:
            log.warning("Could not put PT Kernel in standby")

    else:
        log.debug('Pointing kernel will not be disable...')

    return 0


if __name__ == '__main__':
    parser = create_parser()
    args = parser.parse_args()

    main(args)
