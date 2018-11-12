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
    parser.add_argument('--timeout', dest='timeout', default=5., type=float,
                        help="Command timeout (in seconds).")
    parser.add_argument("--database", dest="database", default=None, type=str,
                        help="Filename with the run database.")

    return parser


def main(args):

    log = logging.getLogger(__name__)
    mgr = SALPY_MTPtg.SAL_MTPtg()
    mgr.salCommand("MTPtg_command_raDecTarget")

    # If pt kernel needs enabling, enable it
    if args.enable:
        log.debug('Enabling PT Kernel...')
        pass
    else:
        log.debug('Pointing kernel will not be enabled...')

    if args.database is None:
        raise IOError('Database must be defined. Use --database <filename.db>.')
    elif not os.path.exists(args.database):
        log.error('File %s does not exists. Specify valid database with --database option.', args.database)
        return -1

    # preparing topic
    myData = SALPY_MTPtg.MTPtg_command_raDecTargetC()
    myData.frame = 1
    myData.epoch = 2000.
    myData.equinox = 2000.

    myData.parallax = 0.
    myData.pmRA = 0.
    myData.pmDec = 0.
    myData.rv = 0.
    myData.dRA = 0.
    myData.dDec = 0.
    myData.rotPA = 0.
    myData.rotFrame = 1
    myData.rotMode = 1

    log.debug('Reading input data from %s', args.database)

    conn = sqlite3.connect(args.database)
    df = pd.read_sql_query("select * from summaryAllProps;", conn)

    log.debug('Got %i targets from database. Starting simulation', len(df))

    buffer = 0.
    for i in range(len(df)):
        ra = df['fieldRA'][i]
        dec = df['fieldDec'][i]
        observation_lst = df['observationStartLST'][i]
        slewtime = df['slewTime'][i]
        exptime = df['visitExposureTime'][i]

        ha = observation_lst - ra  # compute hour angle of the observation

        # now, I need to get the local sidereal time
        now = datetime.datetime.now()
        current_lst = (now.hour + now.minute/60. + now.second/60./60.) * 360. / 24.

        current_ra = current_lst - ha

        log.debug('Target[%i]: %8.2f %8.2f', i+1, current_ra, dec)

        myData.targetName = 'target_%04i' % (i+1)
        myData.targetInstance = i+1
        myData.ra = '%f' % current_ra
        myData.declination = '%f' % dec

        cmdId = mgr.issueCommand_raDecTarget(myData)

        before_cmd_time = time.time()
        retval = mgr.waitForCompletion_raDecTarget(cmdId, args.timeout)
        cmd_time = time.time()-before_cmd_time

        log.debug('Command took %f s', cmd_time)

        # Send target
        log.debug('Slewing (%.2f s)...', slewtime)
        # TODO: loop to get signal from Mount
        time.sleep(slewtime)

        log.debug('Exposing (%.2f s)...', exptime)
        time.sleep(exptime)

        log.debug('Done')

    # at the end, disable pt kernel if requested
    if args.enable:
        log.debug('Disabling PT Kernel...')
        pass
    else:
        log.debug('Pointing kernel will not be disable...')

    return 0


if __name__ == '__main__':
    parser = create_parser()
    args = parser.parse_args()

    main(args)
