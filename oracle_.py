print("HERE I AM, ROCK YOU LIKE A HURRICANE")

from ethInfo import oracleKey,oracleAddress,factoryAddress,factoryAbi,blueprintAbi,verifyEventSig
from web3 import IPCProvider, Web3
import datetime
 
import requests
import time
import numpy as np
import operator

print("imported libraries")

BUFFER_BETWEEN_SCRIPTS = 500
LOG_FILE = '/home/sunspot/Desktop/logolog/oracleLog'+str(time.time())+'.txt'

f= open(LOG_FILE,"w+")
f.close()

print("opened file")

def getBlueprintData(blueprintID):
    global factory, w3
    
    blueprintAddress,_,_,_ = factory.functions.blueprints(blueprintID).call()
    noOfBlueprints = factory.functions.noOfBlueprints().call
    
    blueprintContract = w3.eth.contract(address=blueprintAddress, abi=blueprintAbi)
    
    ticker = blueprintContract.functions.ticker().call()
    creation = blueprintContract.functions.creationTimestamp().call()
    expires = blueprintContract.functions.expirationTimestamp().call()
    
    return (ticker, creation, expires)


def minuteData(ticker, startTimestamp, endTimestamp):

    nDatapoints = (endTimestamp - startTimestamp)/60

    if (((endTimestamp + 7*24*3600) < time.time())|(nDatapoints>2000)):
        return False

    endTimestamp = str(int(endTimestamp))
    nDatapoints = str(int(nDatapoints))

    url = 'https://min-api.cryptocompare.com/data/histominute?fsym='+ticker+'&tsym=USD&limit='+nDatapoints+'&toTs='+endTimestamp    
    response = requests.get(url)

    if (response.json()['Reponse'] == 'Error'):
        return False

    return response.json()['Data']



def hourlyData(ticker, startTimestamp, endTimestamp):

    nDatapoints = (endTimestamp - startTimestamp)/3600

    if (nDatapoints>2000):
        return False

    endTimestamp = str(int(endTimestamp))
    nDatapoints = str(int(nDatapoints))


    url = 'https://min-api.cryptocompare.com/data/histohour?fsym='+ticker+'&tsym=USD&limit='+nDatapoints+'&toTs='+endTimestamp
        
    response = requests.get(url)

    if (response.json()['Response'] == 'Error'):
        return False

    return response.json()['Data']







def dailyData(ticker, startTimestamp, endTimestamp):

    nDatapoints = (endTimestamp - startTimestamp)/(3600*24)

    endTimestamp = str(int(endTimestamp))
    nDatapoints = str(int(nDatapoints))

    url = 'https://min-api.cryptocompare.com/data/histoday?fsym='+ticker+'&tsym=USD&limit='+nDatapoints+'&toTs='+str(int(endTimestamp))
        
    response = requests.get(url)

    if (response.json()['Reponse'] == 'Error'):
        return False

    return response.json()['Data']




def getHighLow (ticker, startTimestamp, endTimestamp):
    
    highs = []
    lows = []
    times = []
    
   
    if(minuteData(ticker,startTimestamp, endTimestamp)!=False):
        priceData = minuteData(ticker,startTimestamp, endTimestamp)
    elif(hourlyData(ticker,startTimestamp, endTimestamp)!=False):
        priceData = hourlyData(ticker,startTimestamp, endTimestamp)
    else:
        priceData = dailyData(ticker,startTimestamp, endTimestamp)
    

    if (priceData != []):
        for price in priceData:
            
            highs.append(price["high"])
            lows.append(price["low"])
            times.append(price["time"])    

        highIndex, high = max(enumerate(highs), key=operator.itemgetter(1))
        highTime = times[highIndex]
        
        lowIndex, low = min(enumerate(lows), key=operator.itemgetter(1))
        lowTime = times[lowIndex]
        
           
        return (high, highTime, low, lowTime)
    else:
        return (-1,-1,-1,-1)



def sendTx(blueprintID, high, highTime, low, lowTime):
    global nonce, factory
                
    txn = factory.functions.verifyBlueprint(
        int(blueprintID),
        int(high*10**6),
        int(highTime),
        int(low*10**6),
        int(lowTime)
    ).buildTransaction({
        'from':oracleAddress,
        'chainId': 3,
        'gas': 314150,
        'gasPrice': w3.toWei('20','gwei'),
        'nonce': nonce
    })
    
    signed = w3.eth.account.signTransaction(txn, oracleKey)
    try:
        w3.eth.sendRawTransaction(signed.rawTransaction)
        nonce += 1
    except:
        f = open(LOG_FILE,'a')
        f.write('\n' + str(datetime.datetime.now()))
        f.write('\n' + "error sending tx to blueprint, ID: "+str(blueprintID))
        f.write('\n')
        f.close()

    time.sleep(20)


if __name__ == '__main__':
    print("start main")
    startTime = time.time()
    runTime = 3600-BUFFER_BETWEEN_SCRIPTS
    endTime = startTime+runTime

    try:
        w3 = Web3(IPCProvider('/home/sunspot/.ethereum/testnet/geth.ipc'))
        nonce = w3.eth.getTransactionCount(oracleAddress) 
        factory = w3.eth.contract(address=factoryAddress, abi=factoryAbi)
        noOfBlueprints = factory.functions.noOfBlueprints().call()

    except:
        f = open(LOG_FILE,'a')
        f.write('\n' + str(datetime.datetime.now()))
        f.write('\n' + "error connecting to factory contract"+str(blueprintID))
        f.write('\n')
        f.close()
        execfile()


    print ("preloop")
    while (time.time()<endTime):
        blueprintsToVerify = []
        event_filter = w3.eth.filter({"address": factoryAddress, "fromBlock":0, "toBlock":"latest"})

        for event in event_filter.get_all_entries():
            if (str(event['topics'])==verifyEventSig):
                #print(int(event['data'][-42:],16))        
                blueprintsToVerify.append(int(event['data'][-42:],16))

        for n in range(noOfBlueprints):
            if ((n+1) not in blueprintsToVerify):
                
                ticker,created,expires = getBlueprintData(n+1)
                
                if (time.time() > expires):
                    blueprintsToVerify.append(n+1)


                    
        for blueprintID in blueprintsToVerify:
            
            ticker,start,expires = getBlueprintData(blueprintID)
            end = min(expires,time.time())
            
            high, highTime, low, lowTime = getHighLow(ticker, start, end)

            if (high != -1):

                f = open(LOG_FILE,'a')
                try:
                    txRx = sendTx(blueprintID, high, highTime, low, lowTime)
                    f.write('\n' + ticker + ", blueprint:"+ str(blueprintID)+", tx receip: " + str(txRx))
                    f.write('\n' + str(high)+", "+ str(highTime)+", "+str(low)+", "+str(lowTime))
                except:
                    f.write('\n' + str(datetime.datetime.now()))
                    f.write('\n' + "Error trying to verify blueprint, ID:"+str(blueprintID))

                
                f.write('\n')
                f.close()

        
        time.sleep(60)
