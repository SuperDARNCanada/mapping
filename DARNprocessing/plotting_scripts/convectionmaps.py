#!/usr/bin/env python

# Copyright 2017 SuperDARN Canada
#
# Marina Schmidt
#
# fitacf2convectionMap.py
# 2018-01-26

from __future__ import print_function

import logging
import shutil
import os
import argparse
import re

from datetime import datetime
from subprocess import call, check_output, CalledProcessError
from glob import glob

from DARNprocessing.utils.utils import (file_exists,
                                        check_rst_command,
                                        flag_options,
                                        path_exists)

from DARNprocessing.utils.convectionMapConstants import (ErrorCodes,
                                                         NorthRadar,
                                                         SouthRadar,
                                                         CanadianRadar,
                                                         RstConst,
                                                         RadarConst)

from DARNprocessing.utils.convectionMapWarnings import (ConvertWarning,
                                                        OmniFileNotFoundWarning,
                                                        EmptyDataFileWarning,
                                                        FileNotFoundWarning,
                                                        OmniBadDataWarning,
                                                        OmniFileNotGeneratedWarning)

from DARNprocessing.utils.convectionMapExceptions import (NoGridFilesException,
                                                          OmniException,
                                                          RSTException,
                                                          RSTFileEmptyException,
                                                          PathDoesNotExistException)

from DARNprocessing.IMF_scripts.omni import Omni


class ConvectionMaps():
    """
    Convection Maps is a python class the wraps around the RST commands to
    generate the following files:
        - grid files
        - map files
        - convection potential plots

    WARNING! Does not take in fit files, please makes sure your data is one
    of the following types:
            - fitacf
            - lmfit2

    If you are using fit files, please read fit2fitacf, generate_fitacf_files or
    generate_lmfit2_files.
    * Currently not implemented *
    """

    def __init__(self, arguements=None, parameters=None):
        """
        Reads in user command line options and parses them to correct member
        fields.

        :param arguements: sys.args from command line
        :param parameters: Dictionary of the command line arguements; used for testing or
               python scripts
                key name: defualt value
                -----------------------
                'date': None,
                'channel': 5,
                'hemisphere': 'north',
                'start_time': '00:00',
                'end_time': 23:59,
                'image_ext': 'pdf',
                'integration_time': 120,
                'data_path': self._current_path,
                'plot_path': self._current_path,
                'map_path': self._current_path,
                'key_path': self._current_path,
                'num_proc': 1

        :raise ValueError: date parameter is required

        """

        self._current_date = datetime.now()
        self._current_path = os.getcwd()

        if not parameters:
            self.arguement_parser(arguements)
        else:
            self.parameter = {'date': None,
                              'channel': 5,
                              'integration_time':120,
                              'hemisphere': 'north',
                              'start_time': '00:00',
                              'end_time': '23:59',
                              'rst_version': 4.1,
                              'image_ext': 'pdf',
                              'logfile': self._current_path + \
                                         '/ConvectionMaps.log',
                              'data_path': self._current_path,
                              'plot_path': self._current_path,
                              'map_path': self._current_path,
                              'map_path': self._current_path,
                              'key_path': self._current_path,
                              'num_proc': 1}

            self.parameter.update(parameters)
            # Required field
            if not self.parameter['date']:
                raise ValueError("Date of the date was not passed in, please"
                                 "include in the parameters dictionary")

        # check if the data path exists otherwise we cannot porceed.
        path_exists(self.parameter['data_path'])

        # the possible letter channels that a fitted file names can contain
        # that pertains to the stero channel value. Most used by alaskian radars.
        self.channel = ['', 'a', 'b', 'c', 'd']

        # Logging information setup
        FORMAT = "%(levelname)s %(asctime)-15s: %(message)s"
        logging.basicConfig(filename=self._current_path +\
                            self.parameter['logfile'],
                            format=FORMAT,
                            level=logging.DEBUG)
        logging.info("Parameter list:" + str(self.parameter))

        # Generate map path and plot path if they do not exist
        self._generate_paths()

        # TODO clean up rst options and make it a requirement to use only rst 4.0 and higher
        self.rst_options = ""

        # Logging information on radars used, missing and ones the gave errors
        # during gridding process
        self.radars_used = "Radar files uses in the Convection Map process:\n"
        self.radars_missing = "Radar files missing"\
                              " (not used in the Convection Map process):\n"
        self.radars_errors = "Radars files that raised errors:\n"

    # TODO: Look for more possible options to add here for changing convection maps
    def arguement_parser(self, arguements):
        """
        Arguement parser - parses the arguement passed into the script into a
                    parameter dictionary.

            :param arguements: sys.args
        """

        # Note: -h is reserved for --help feature thus -H for hemisphere
        option_names = [('date'),
                        ('-c','--channel'),
                        ('-i','--integration-time'),
                        ('-H','--hemisphere'),
                        ('-s','--start-time'),
                        ('-e','--end-time'),
                        ('-x','--image-ext'),
                        ('-l','--logfile'),
                        ('-f','--data-format'),
                        ('-d','--data-path'),
                        ('-p','--plot-path'),
                        ('-m','--map-path'),
                        ('-k','--key-path'),
                        ('-v','--verbose')]
        option_settings = [{'type':str,
                            'metavar':'YYYYMMDD',
                            'help':'The date of the fitacf data.'},
                           {'type':int,
                            'choices':[0, 1, 2, 3, 4, 5],
                            'default':5,
                            'help':'Select the channel number of data'
                            ' to use for the convection map process.'
                            ' Default: 5 - use all channels'},
                           {'type':int,
                            'default':'120',
                            'help':'Integration time between each plot in seconds.'
                            ' Default: 120 - 2 minute convection plots'},
                           {'type':str,
                            'choices':['north', 'south','Canadian'],
                            'default':'north',
                            'help':'The hemisphere you want to assimilate.'
                            ' Default: north'},
                           {'type':str,
                            'metavar':'hh:mm',
                            'default':'00:00',
                            'help':'The start time at hh:mm of the fitacf data.'
                            ' Default: 00:00'},
                           {'type':str,
                            'metavar':'hh:mm',
                            'default':'23:59',
                            'help':'The end time at hh:mm of the fitacf data.'
                            ' Default: 23:59'},
                           {'type':str,
                            'metavar':'EXTENSION',
                            'default':'png',
                            'help':'The image format of convection maps.'
                            ' Default: pdf'},
                           {'type':str,
                            'metavar':'PATH',
                            'default':self._current_path+'/ConvectionMaps.log',
                            'help':'The absolute path to the log file'
                            ' Default: {}/ConvectionMaps.log'
                            ''.format(self._current_path)},
                           {'type':str,
                            'metavar':'PATH',
                            'default':self._current_path,
                            'help':'The absolute path to the fitted data.'
                            ' Default: {}'.format(self._current_path)},
                           {'type':str,
                            'metavar':'PATH',
                            'default':self._current_path,
                            'help':'The absolute path to where the convection'
                            ' maps will be saved.'
                            ' Default: {}'.format(self._current_path)},
                           {'type':str,
                            'metavar':'PATH',
                            'default':self._current_path,
                            'help':'The absolute path to where the map files'
                            ' will be saved to.'
                            ' Default: {}'.format(self._current_path)},
                           {'type':str,
                            'metavar':'PATH',
                            'default':self._current_path,
                            'help':"The absolute path to the key file for"
                            "the convection maps."
                            " Default: {}".format(self._current_path)},
                           {'action':'store_true',
                            'help':'Turns on verbose mode.'}]
        self.parameter = flag_options('fitacf2convectionmap',
                                      'Converts fitted data files to convection maps',
                                      option_names,
                                      option_settings)

    def set_data_path(self, new_data_path):
        """
        set the data path, used when the user wants to change the data path half
        way through but does not want to reinput all the setting info.

        Example of usage: comparison betweeen lmfit2 and fitacf files

            :param new_data_path: str of the new data path
        """
        self.parameter['data_path'] = new_data_path
        path_exists(self.parameter['data_path'])

    def set_date(self,new_date):
        """
        set the date, used when the user wants to change the date without
        changing the other settings.

            :param new_date: str in the format YYYYMMDD of the new date
        """
        self.parameter['date'] = new_date

    def set_plot_path(self, new_plot_path):
        """
        set the plot_path, used when the user wants to change the plot path
        without changing the other settings.

            :param new_plot_path: str the new plot path
        """
        self.parameter['plot_path'] = new_plot_path
        self._generate_paths()

    def set_hemisphere(self, new_hemisphere):
        """
        set the hemisphere, used when the user wants to change the hemisphere
        without changing the other settings.

            :param new_hemisphere: ['north','south','Canadian']
                                   the new hemisphere
        """
        if new_hemisphere not in ['north','south','Canadian']:
            raise ValueError("{hemisphere} is not of the following options:"
                             " north, south, Canadian"
                             "".format(hemisphere=new_hemisphere))
        self.parameter['hemisphere'] = new_hemisphere

    # TODO: finish other set functions.


    def _generate_paths(self):
        """
        generate the folder paths for the various file paths
        """
        for path in [self.parameter['plot_path'],
                     self.parameter['map_path']]:
            try:
                path_exists(path)
            except PathDoesNotExistException as err:
                try:
                    os.makedirs(path)
                except OSError as err:
                        raise OSError(err)

        logging.info("The following data files will be"
                     " stored in the following paths")
        logging.info("Plot path: " + self.parameter['plot_path'])
        logging.info("Map files path: " + self.parameter['map_path'])
        logging.info("Omni files path: " + self.parameter['map_path'])
        logging.info("The data for the convections maps is obtained from")
        logging.info("Data path: " + self.parameter['data_path'])

    # TODO: implement parallel version
    def _generate_radar_grid_file(self, radar_abbrv, data_path):
        """
        Helper function for generate_grid_files to generate a grid file(s) for
        a single radar extension. This can be used to parallelize the grid
        generation process.
        """
        # TODO: delete it if glob works for getting any type of file name
        # data_filename = "{date}{ext}".format(date=self.parameter['date'],
        #                                      ext=radar_ext)

        data_filename = os.path.basename(data_path)

        # Standard naming convention for grid files
        grid_filename = "{date}.{abbrv}.grid".format(date=self.parameter['date'],
                                                     abbrv=radar_abbrv)

        grid_path = "{data_path}/{grid_file}"\
                    "".format(data_path=self.parameter['plot_path'],
                              grid_file=grid_filename)

        # if the data file is not in the current file then check in the
        # in the provided data folder.
        if os.path.isfile(data_path):
            try:
                shutil.copy2(data_path,
                             self.parameter['plot_path']+'/'+data_filename)
            except shutil.Error as msg:
                logging.warn(msg)

            data_path = self.parameter['plot_path']+'/'+data_filename

            # unzip any possible compression formats...
            # TODO: replace this with a dictionary to key in for various compression types
            #       and the dictionary lives in the constants file so that the user changes that file
            #       not this file
            if 'gz' in data_path:
                gzip_command = "gzip -df {data_path}"\
                               "".format(data_path=data_path,
                                         plot_path=self.parameter['plot_path'])
                if call(gzip_command, shell=True) != 0:
                    logging.warn(FileNotFoundWarning(data_filename))
                    self.radars_errors += data_filename + '\n'
                    return ErrorCodes.ERRFILENOTFOUND
                data_filename = data_filename.strip('.gz')

            elif 'bz2' in data_path:
                bzip2_command = "bzip2 -dfv {data_path}"\
                                "".format(data_path=data_path,
                                          plot_path=self.parameter['plot_path'])
                if call(bzip2_command, shell=True) != 0:
                    logging.warn(FileNotFoundWarning(data_filename))
                    self.radars_errors += data_filename + '\n'
                    return ErrorCodes.ERRFILENOTFOUND
                data_filename = data_filename.strip('.bz2')

        else:
            logging.warn("{datafile} was not found in the data_path: {data_path}"
                         " or plot_path: {plot_path}, this file will not be used"
                         "in the convection map process"
                         "".format(data_path=self.parameter['data_path'],
                                   datafile=data_filename,
                                   plot_path=self.parameter['plot_path']))
            self.radars_missing += data_filename + '\n'
            message = "File {datafile} was not found, please make sure to"\
                      " provide data path using -d option and that the"\
                      " file exist in the folder"
            raise OSError(message)

        data_path = self.parameter['plot_path']+'/'+data_filename

        if os.path.getsize(data_path) == 0:
            logging.warn(EmptyDataFileWarning(data_filename))
            self.radars_errors += data_filename + '\n'
            return ErrorCodes.ERREMPTYFILE

        # TODO: maybe remove fit checking and make it a requirement and write a wrapper to convert fit files.
        #       this is a hassel to check :( and really we should just archive fit files and convert to the most current file type
        if 'C.fit' in data_filename:
            try:
                data_path, radar_abbrv = self.convert_fit_to_fitacf(data_path)
            except RSTException as err:
                logging.exception(err)
                return ErrorCodes.ERRRST

        dmapdump_command = "dmapdump {} | grep -c '\"scan\" = -1'"\
                           "".format(data_path)

        grid_options = self.rst_options + ' -i ' + \
            str(self.parameter['integration_time'])

        # We need this try/except block because grep will return a non-zero
        # exit value even if there is no error, example) if there is no match
        # it will return 1
        # check_output will throw an exception on non-zero return values
        try:
            neg_scan_flag = check_output(dmapdump_command, shell=True)
        except CalledProcessError as e:
            neg_scan_flag = e.output  # Gets the output of the command
        # Hopefully in the near RST future this situation
        # would be handled more gracefully
        if int(neg_scan_flag) > 0:
            # TODO: this may not be needed in the newest version of RST
            grid_options += "-tl 60 "

        channelA = self._check_for_channel(data_path, 1)
        channelB = self._check_for_channel(data_path, 2)
        monochannel = self._check_for_channel(data_path, 0)

        data_filename = os.path.basename(data_path)
        if '.a.' in data_filename:
            grid_options = grid_options + " -cn_fix a"
        elif '.b.' in data_filename:
            grid_options = grid_options + " -cn_fix a"
        elif '.c.' in data_filename:
            grid_options = grid_options + " -cn_fix c"
        elif '.d.' in data_filename:
            grid_options = grid_options + " -cn_fix d"
        elif self.parameter['channel'] == 0:
                grid_path = "{plot_path}/{date}.{abbrv}."\
                            "grid".format(date=self.parameter["date"],
                                          plot_path=self.parameter['plot_path'],
                                          abbrv=radar_abbrv)
        elif self.parameter['channel'] == 1:
                grid_path = "{plot_path}/{date}.{abbrv}.a."\
                            "grid".format(date=self.parameter["date"],
                                          plot_path=self.parameter['plot_path'],
                                          abbrv=radar_abbrv)
                grid_options = grid_options + " -cn A"
        elif self.parameter['channel'] == 2:
                grid_path = "{plot_path}/{date}.{abbrv}.b."\
                            "grid".format(date=self.parameter["date"],
                                          plot_path=self.parameter['plot_path'],
                                          abbrv=radar_abbrv)
                grid_options = grid_options + " -cn B"
        else:
            if monochannel > 0:
                grid_path = "{plot_path}/{date}.{abbrv}."\
                            "grid".format(date=self.parameter["date"],
                                          plot_path=self.parameter['plot_path'],
                                          abbrv=radar_abbrv)
                self.make_grid(data_path, grid_path, grid_options)

            if channelA > 0:
                grid_path = "{plot_path}/{date}.{abbrv}.a."\
                            "grid".format(date=self.parameter["date"],
                                          plot_path=self.parameter['plot_path'],
                                          abbrv=radar_abbrv)
                grid_optionsA = grid_options + " -cn A"
                self.make_grid(data_path, grid_path, grid_optionsA)

            if channelB > 0:
                grid_path = "{plot_path}/{date}.{abbrv}.b."\
                            "grid".format(date=self.parameter["date"],
                                          plot_path=self.parameter['plot_path'],
                                          abbrv=radar_abbrv)
                grid_optionsB = grid_options + " -cn B"
                self.make_grid(data_path, grid_path, grid_optionsB)
            return 0

        self.make_grid(data_path, grid_path, grid_options)
        return 0

    # Maybe move this function to utils?
    def _check_for_channel(self, data_file, channel_num):
        """
        A method to check for the channel number in a fitacf file
        that may use mono and stero.
        """
        channel_command = "dmapdump {filename} "\
                          "| grep -c '\"channel\" = {channel}'"\
                          "".format(filename=data_file,
                                    channel=channel_num)
        try:
            channel_count = check_output(channel_command, shell=True)
        except CalledProcessError as e:
            channel_count = e.output  # Gets the output of the command
        return int(channel_count)

    def make_grid(self, data_file, grid_file, grid_options=""):
        make_grid_command = "make_grid {gridoptions} -xtd"\
                            " -i {integration_time} -minrng 2"\
                            " -vemax {max_velocity}"\
                            " {datafile} > {gridpath}"\
                            "".format(gridoptions=grid_options,
                                      integration_time=RstConst.INTEGRATION_TIME,
                                      max_velocity=RstConst.VEMAX,
                                      datafile=data_file,
                                      gridpath=grid_file)

        logging.info(make_grid_command)
        try:
            check_rst_command(make_grid_command, grid_file)
        except RSTException as err:
            logging.warn(err)
            self.radars_errors += data_file + '\n'
        except RSTFileEmptyException as err:
            self.radars_errors += data_file + '\n'
            logging.warn(err)
            os.remove(grid_file)

    # TODO: might be a util method
    def convert_fit_to_fitacf(self, file_path):
        """
        Converts fit data to fitacf with the standard naming convention used for
        superDARN data.
        Retruns the fitacf filename that the fit data was saved to and the radar
        abbrevation associated to the letter.
        """
        match = re.search(r'([a-z])', os.path.basename(file_path))
        radar_letter = match.group()
        if self.parameter['hemisphere'] == 'south':
            radar_abbrv = SouthRadar.SINGLE_TO_ABBRV[radar_letter]
        else:
            radar_abbrv = NorthRadar.SINGLE_TO_ABBRV[radar_letter]

        fitacf_path = "{plot_path}/{date}.C0.{abbrv}."\
                      "fitacf".format(date=self.parameter['date'],
                                      abbrv=radar_abbrv,
                                      plot_path=self.parameter['plot_path'])
        fittofitacf_command = "fittofitacf {filepath} >"\
                              " {fitacf_filename}"\
                              "".format(filepath=file_path,
                                        fitacf_filename=fitacf_path)
        check_rst_command(fittofitacf_command, fitacf_path)

        return (fitacf_path, radar_abbrv)

    # TODO: need to determine what wrappers should be where ... hmmm

    # TODO: implement a method to generate fitacf files from rawacf files
    def generate_fitacf_files(self):
        pass

    # TODO: implement a method to convert rawacf to lmfit using Ashton's code
    def generate_lmfit_files(self):
        pass

    def concatinate_fitted_date(self):
        pass

    def generate_grid_files(self):
        """
        Generates the grid files used in the map generation step.
        """
        radar_abbrv = []
        if self.parameter['hemisphere'] == 'south':
            radar_abbrv = SouthRadar.RADAR_ABBRV
        elif self.parameter['hemisphere'] == 'canadian':
            radar_abbrv = CanadianRadar.RADAR_ABBRV
        else:
            radar_abbrv = NorthRadar.RADAR_ABBRV

        # TODO: need to handle fit files...
        grid_file_counter = 0
        for ext in RadarConst.FILE_TYPE:
            for abbrv in radar_abbrv:
                file_pattern = "{data_path}/{date}*{abbrv}*.{ext}*"\
                               "".format(data_path=self.parameter['data_path'],
                                         date=self.parameter['date'],
                                         abbrv=abbrv,
                                         ext=ext)
                for filename in glob(file_pattern):
                    if self._generate_radar_grid_file(abbrv, filename) == 0:
                        grid_file_counter += 1

        logging.info(self.radars_used)
        logging.info(self.radars_missing)
        logging.info(self.radars_errors)

        if grid_file_counter == 0:
            logging.error(NoGridFilesException)
            raise NoGridFilesException(radar_abbrv)

        grd_filename = "{date}.grd".format(date=self.parameter['date'])
        grd_path = "{plot_path}/{grd_file}"\
                   "".format(plot_path=self.parameter['plot_path'],
                             grd_file=grd_filename)

        combine_grid_command = "combine_grid {options} {plot_path}/{date}.*.grid"\
                               " > {grdpath}"\
                               "".format(options=self.rst_options,
                                         plot_path=self.parameter['plot_path'],
                                         date=self.parameter['date'],
                                         grdpath=grd_path)

        check_rst_command(combine_grid_command, grd_path)

    def generate_map_files(self):
        """
        Generates the various map files for the radar fit/fitacf files availible for
        the given date and hemisphere. The 'date.map' is the only saved file,
        the other map files are removed at the end of the convection process.
        """
        map_grd_options = ""

        if self.parameter['hemisphere'] == "south":
            map_grd_options = self.rst_options + " -sh"

        grd_path = "{plot_path}/{date}.grd"\
                   "".format(plot_path=self.parameter['plot_path'],
                             date=self.parameter['date'])
        file_exists(grd_path)
        empty_map_filename = "{date}.empty.map"\
                             "".format(date=self.parameter['date'])
        empty_map_path = "{plot_path}/{empty_map}"\
                         "".format(plot_path=self.parameter['plot_path'],
                                   empty_map=empty_map_filename)

        map_grd_command = "map_grd {options} -l 50 {plot_path}/{date}.grd > "\
                          "{plot_path}/{filename}"\
                          "".format(options=map_grd_options,
                                    plot_path=self.parameter['plot_path'],
                                    date=self.parameter['date'],
                                    filename=empty_map_filename)\

        check_rst_command(map_grd_command, empty_map_path)

        hmb_map_filename = "{date}.hmb.map".format(date=self.parameter['date'])
        hmb_map_path = "{plot_path}/{hmb_map}"\
                       "".format(plot_path=self.parameter['plot_path'],
                                 hmb_map=hmb_map_filename)

        map_addhmb_command = "map_addhmb {options} {plot_path}/{empty_map} >"\
                             " {plot_path}/{hmb_map}"\
                             "".format(options=self.rst_options,
                                       plot_path=self.parameter['plot_path'],
                                       empty_map=empty_map_filename,
                                       hmb_map=hmb_map_filename)

        check_rst_command(map_addhmb_command, hmb_map_path)

        omni = Omni(self.parameter['date'], self.parameter['map_path'])

        try:
            update = omni.check_for_updates()
            if update:
                old_omni_file = "{map_path}/{date}_omni_{currentdate}.txt"\
                                "".format(date=self.parameter['date'],
                                          currentdate=self._current_date.strftime("%Y%m%d"))
                try:
                    shutil.move(omni.omni_path, old_omni_file)
                except IOError as err:
                    logging.exception(err)
                    pass
        except OmniFileNotFoundWarning as warning_msg:
            logging.warn(warning_msg)
            update = True

        try:
            if update:
                omni.get_omni_file()

            omni.omnifile_to_IMFfile()

            imf_map_filename = "{date}.imf.map"\
                               "".format(date=self.parameter['date'])
            imf_map_path = "{map_path}/{imf_map}"\
                           "".format(map_path=self.parameter['map_path'],
                                     imf_map=imf_map_filename)

            map_addimf_command = "map_addimf {options} -omni -d 00:10"\
                                 " -if {map_path}/{imf_filename}"\
                                 " {plot_path}/{hmb_map} >"\
                                 " {plot_path}/{imf_map}"\
                                 "".format(options=self.rst_options,
                                           map_path=self.parameter['map_path'],
                                           plot_path=self.parameter['plot_path'],
                                           imf_filename=omni.imf_filename,
                                           hmb_map=hmb_map_filename,
                                           imf_map=imf_map_filename)

            check_rst_command(map_addimf_command, imf_map_path)
            self._imf_option = " -imf"
            input_model_file = imf_map_filename

        except OmniException as err_msg:
            logging.error(err_msg)
            self._imf_option = ""
            input_model_file = hmb_map_filename

        except (OmniFileNotGeneratedWarning,
                OmniFileNotFoundWarning,
                OmniBadDataWarning) \
                as warning_msg:
            logging.warn(warning_msg)
            self._imf_option = ""
            input_model_file = hmb_map_filename

        map_model_filename = "{date}.model.map"\
                             "".format(date=self.parameter['date'])
        map_model_path = "{plot_path}/{map_model}"\
                         "".format(plot_path=self.parameter['plot_path'],
                                   map_model=map_model_filename)

        map_addmodel_command = "map_addmodel {options} -o 8 -d l "\
                               "{plot_path}/{input_map} > {plot_path}/{model_map}"\
                               "".format(options=self.rst_options,
                                         plot_path=self.parameter['plot_path'],
                                         input_map=input_model_file,
                                         model_map=map_model_filename)
        check_rst_command(map_addmodel_command, map_model_path)

        map_filename = "{date}.map".format(date=self.parameter['date'])
        map_path = "{plot_path}/{map_file}"\
                   "".format(plot_path=self.parameter['plot_path'],
                             map_file=map_filename)

        map_fit_command = "map_fit {options} {plot_path}/{model_map} >"\
                          " {plot_path}/{map_file}"\
                          "".format(options=self.rst_options,
                                    plot_path=self.parameter['plot_path'],
                                    model_map=map_model_filename,
                                    map_file=map_filename)
        check_rst_command(map_fit_command, map_path)
        try:
            shutil.copy2(map_path, self.parameter["map_path"])
        except shutil.Error:
            pass

    def generate_RST_convection_maps(self):
        """
        Generates the convection maps using the RST map_plot function.
        """

        logging.info("Generating Convection Maps uring RST ")
        # TODO: A better method of importing the key file and
        # what to do when it is not provided
        shutil.copy2("{}/rainbow.key".format(self.parameter['key_path']), self.parameter['plot_path'])
        key_option = "-vkeyp -vkey_path {}/ -vkey rainbow.key"\
                     "".format(self.parameter['plot_path'])
        map_path = "{map_path}/{date}.map"\
                   "".format(map_path=self.parameter['map_path'],
                             date=self.parameter['date'])

        post_script_path = "{}/*.ps".format(self.parameter['plot_path'])
        file_exists(map_path)
        map_plot_command = "map_plot {options} -ps -mag"\
                           " -st {start_time} -et {end_time} -rotate -hmb -modn"\
                           " -fit -grd -ctr {imf} -dn -extra -coast -vecp "\
                           " -pot -time {key} -path {plot_path} {map_path}"\
                           " 2>/dev/null"\
                           "".format(options=self.rst_options,
                                     start_time=self.parameter['start_time'],
                                     end_time=self.parameter['end_time'],
                                     imf=self._imf_option,
                                     key=key_option,
                                     plot_path=self.parameter['plot_path'],
                                     map_path=map_path)
        logging.info(map_plot_command)
        check_rst_command(map_plot_command, post_script_path)

        for ps_file in glob(post_script_path):
            image_filename = ps_file.replace(".ps", "")
            convert_command = "convert -density 200 {ps_filename} "\
                              " {filename}.{ext}"\
                              "".format(plot_path=self.parameter['plot_path'],
                                        ps_filename=ps_file,
                                        filename=image_filename,
                                        ext=self.parameter['image_ext'])
            return_value = call(convert_command.split())
            if return_value != 0:
                logging.warn(ConvertWarning(ps_file,
                                            self.parameter['image_ext']))

    def cleanup(self):
        """
        Cleans up any meta or data that should not be stored in the plot path.
        """
        path = "{plot_path}/{date}".format(plot_path=self.parameter['plot_path'],
                                          date=self.parameter['date'])

        for f in glob(path+'*.grid'):
            os.remove(f)
        for f in glob(path+'*.map'):
            os.remove(f)
        for ext in RadarConst.FILE_TYPE:
            for f in glob('{path}*.{ext}*'.format(path=path, ext=ext)):
                os.remove(f)
        os.remove(path + ".grd")


if __name__ == '__main__':
    import sys
    convec = ConvectionMaps(sys.argv[1:], 201803)
    # convec.setup_paths()
    convec.generate_grid_files()
    convec.generate_map_files()
    convec.generate_RST_convection_maps()
