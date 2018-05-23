# Copyright 2017 SuperDARN Canada
#
# Marina Schmidt
#
# warning.py
# 2018-01-26


class OmniFileNotGeneratedWarning(Warning):

    def __init__(self, omni_filename, date):
        self.date = date
        self.omni_filename = omni_filename
        self.message = "Omni file: {filename}, was not generated for the "\
                " date {date}. The omni data will not be used in the"\
                " convection map  process".format(filename=self.omni_filename,
                                                  date=self.date )
        Warning.__ini__(self, self.message)


class OmniFileNotFoundWarning(Warning):

    def __init__(self, omni_filename):
        self.omni_filename = omni_filename
        self.message = "{} file found was"\
                " not found. The omni data will not be used in"\
                " in the convection map process.".format(self.omni_filename)
        Warning.__init__(self, self.message)


class OmniBadDataWarning(Warning):

    def __init__(self, date):
        self.date = date
        self.message = "The IMF file for the date {} "\
                " was not generated because there was no good data "\
                " in the omni file".format(self.date)
        Warning.__init__(self, self.message)

class EmptyDataFileWarning(Warning):

    def __init__(self, data_file):
        self.data_filename = data_file
        self.message = "Data file {} is Empty, will not be used in the"\
                " gridding process".format(self.data_filename)
        Warning.__init__(self, self.message)

class FileNotFoundWarning(Warning):

    def __init__(self, data_file):
        self.data_filename = data_file
        self.message = "Data file {} does not exist, will not be used in the"\
                "convection map process".format(self.data_filename)
        Warning.__init__(self, self.message)


class ConvertWarning(Warning):

    def __init__(self, ps_file, extension):
        self.ps_file = ps_file
        self.extension = extension

        self.message = "Warning: convert command could not convert "\
                "{ps_filename} to {ext} format".format(ps_filename=ps_file,
                                                       ext=extension)
        Warning.__init__(self, self.message)