### This file houses plugins
import pandas as pd
import time
from coffea import processor
from coffea.nanoevents import NanoEventsFactory, NanoAODSchema

#if using LPC dask or running locally use 'root://cmsxrootd.fnal.gov/'
#is using coffea casa use 'root://xcache/'

import os
def checkdir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


#reads in files and adds redirector, can specify year, default is all years
def handleData(jsonFile, redirector, year = '', testing = True, data = False):
    if data == True:
        inputs = 'JetHT_data'
        qualifier = str(year)
    else: 
        inputs = 'QCD_binned'
        qualifier = 'UL' + str(year)[-2]
        print(qualifier)
    df = pd.read_json(jsonFile) 
    dict = {}
    for key in df[inputs].keys():
        if qualifier in key:
            print(key)
            if testing:
                dict[key] = [redirector +  df[inputs][key][0]]
            else:
                dict[key] = [redirector + df[inputs][key][i] for i in range(len(df[inputs][key]))]
    return dict

#initiate dask client and run coffea job
from dask.distributed import Client

def runCoffeaJob(processor_inst, jsonFile, dask = False, casa = False, testing = False, year = '', data = False):
    #default is to run locally
    tstart = time.time()
    executor = processor.futures_executor
    if casa:
        redirector = 'root://xcache/'
    else:
        redirector = 'root://cmsxrootd.fnal.gov/'
    exe_args = {"schema": NanoAODSchema, 'skipbadfiles': True,}
    samples = handleData(jsonFile, redirector, year = year, testing = testing, data = data)
    client = None
    cluster = None
    if casa and dask:
        print("Running on coffea casa")
        from coffea_casa import CoffeaCasaCluster
        from dask.distributed.diagnostics.plugin import UploadDirectory #do i need this?
        # client = Client("tls://lauren-2emeryl-2ehay-40cern-2ech.dask.cmsaf-prod.flatiron.hollandhpc.org:8786")
        cluster = CoffeaCasaCluster(cores=11, memory="100 GiB", death_timeout = 60)
        cluster.adapt(minimum=2, maximum=14)
        client = Client(cluster)
        print(client)
        exe_args = {
            "client": client,
            'skipbadfiles':True,
            "schema": NanoAODSchema,
            "align_clusters": True,
        }
        executor = processor.dask_executor
    elif casa == False and dask:
        print("Running on LPC Condor")
        from lpcjobqueue import LPCCondorCluster
        cluster = LPCCondorCluster(shared_temp_directory="/tmp")
        #### minimum > 0: https://github.com/CoffeaTeam/coffea/issues/465
        cluster.adapt(minimum=1, maximum=10)
        client = Client(cluster)
        exe_args = {
            "client": client,
            'skipbadfiles':True,
            "savemetrics": True,
            "schema": NanoAODSchema,
            "align_clusters": True,
        }
#         print("Waiting for at least one worker...")
        client.wait_for_workers(1)
        executor = processor.dask_executor
    else:
        print("Running locally")
    # samples = {'/JetHT/Run2018A-UL2018_MiniAODv2_NanoAODv9-v2/NANOAOD': ['root://xcache//store/data/Run2018A/JetHT/NANOAOD/UL2018_MiniAODv2_NanoAODv9-v2/100000/00AA9A90-57AA-D147-B4FA-54D6D8DA0D4A.root']}
    # samples = {"/QCD_Pt_1800to2400_TuneCP5_13TeV_pythia8/RunIISummer20UL17NanoAODv9-106X_mc2017_realistic_v9-v1/NANOAODSIM":["root://xcache//store/mc/RunIISummer20UL18NanoAODv9/QCD_Pt_470to600_TuneCP5_13TeV_pythia8/NANOAODSIM/106X_upgrade2018_realistic_v16_L1v1-v1/130000/04101AE0-F4F7-364B-9089-BEE9156A0C69.root"]}
    print("Samples = ", samples, " executor = ", executor)
    result = processor.run_uproot_job(samples,
                                      "Events",
                                      processor_instance = processor_inst,
                                      executor = executor,
                                      executor_args = exe_args,
                                     )
    elapsed = time.time() - tstart
    print(result)
    print("Time taken to run over samples ", elapsed)
    return result