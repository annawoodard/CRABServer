from WMCore.Configuration import Configuration
config = Configuration()

#General Section
config.section_("General")
config.General.requestName = 'CHANGE'
config.General.workArea = 'CHANGE'
config.General.transferOutputs = True
config.General.transferLogs = True
config.General.instance = 'preprod'

#Job Type Section
config.section_("JobType")
config.JobType.pluginName = 'Analysis'
config.JobType.psetName = 'psets/pset_use_parent.py'

#Data Section
config.section_("Data")
config.Data.inputDataset = '/SingleMu/Run2015B-17Jul2015-v1/MINIAOD'
config.Data.inputDBS = 'global'
config.Data.splitting = 'LumiBased'
config.Data.unitsPerJob = 20 # 200
config.Data.secondaryDataset = '/SingleMu/Run2015B-v1/RAW'
config.Data.ignoreLocality = False

#Site Section
config.section_("Site")
config.Site.storageSite = 'CHANGE'

