import os
import salobj
import SALPY_atcamera
import time
import numpy as np
import datetime
import nest_asyncio
nest_asyncio.apply()
import asyncio

import logging
logging.getLogger().setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO,
                format='[%(asctime)s] [%(name)-12s:%(lineno)-4d] [%(levelname)-8s]: %(message)s',
                datefmt='%m-%d %H:%M:%S')

def getFileName():
    tmp_file='/tmp/atcamera_filename_current.dat'
    # This function assumes the file created in tmp_file
    # was written by this function. No error handling exists should the file be
    # modified or created via another method.

    def timeStamped(fname_suffix, fmt='AT-O-%Y%m%d-{fname:05}'):
        return (datetime.datetime.now().strftime(fmt).format(fname=fname_suffix))

    # today's format
    number=0 # assume zero for the moment
    file_date = timeStamped(number).split('-')[2]

    # Check to see if a file exists with a past filename
    if os.path.exists(tmp_file):
        # read in the file
        fh = open(tmp_file, 'r')
        first_line = (fh.readline())
        logging.info('Previous line in existing file {}'.format(first_line))

        # check to see if the date is the same
        logging.debug('file_date is: {}'.format(file_date))
        logging.debug('first_line is: {}'.format(first_line))
        if file_date in first_line:
            # grab file number and augment it
            old_num = first_line.split(',')[1]
            logging.debug('Previous Image number was: {}'.format(old_num))
            number = 1+int(old_num)
            logging.info('Incrementing from file to: {}'.format(number))
            fh.close()

        # Delete the file
        os.remove(tmp_file)

    # write a file with the new data
    fh = open(tmp_file, 'w')
    lines_of_text = [str(file_date)+','+str(number)]
    fh.writelines(lines_of_text)
    fh.close()

    fname = timeStamped(number)
    print('Newly generated filename: {}'.format(fname))
    return(fname)

class TakeImageStressTest:
    def __init__(self):
        self.atcamera = salobj.Remote(SALPY_atcamera, f'atcamera')
        
    async def takeImageLoop(self, nimages):

        for i in range(nimages):
            exposure = 1.+np.random.random()*5.
            atcamera_fname = getFileName()
            take_image_topic = self.atcamera.cmd_takeImages.DataType()
            take_image_topic.numImages = 1
            take_image_topic.expTime = exposure
            take_image_topic.shutter = False
            take_image_topic.imageSequenceName = str(atcamera_fname)
            take_image_topic.science = True

            end_readout = self.atcamera.evt_endReadout.next(flush=True, 
                                                            timeout=exposure+30.)
            take_image_task = self.atcamera.cmd_takeImages.start(take_image_topic)

            image = await asyncio.gather(end_readout, take_image_task)

            logging.info('[%04i/%04i] %s (%+03i, %04i, %s)', 
                         i+1, nimages,
                         image[0].imageName,
                         image[1].ack,
                         image[1].error,
                         image[1].result)

seq = TakeImageStressTest()

loop = asyncio.get_event_loop()

logging.info('Start')
loop.run_until_complete(seq.takeImageLoop(100))
logging.info('Done')
