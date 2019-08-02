#!/usr/bin/env python3

import json, requests

debug = False

port = 9092
user = 'test'
pw = 'tset'

def debugDump(label, data):
	if not debug: return
	print(label, json.dumps(data, sort_keys=True, indent=4))

def sendRequest(function, data = None):
	url = 'http://127.0.0.1:' + str(port) + function

	debugDump('POST: ' + url, data)
	resp = requests.post(url=url, json=data, auth=(user, pw))

	# gracefully add 401 error
	if resp.status_code == 401:
		return {'retval': False}

	debugDump('RESP', resp.json())
	return resp.json()



if __name__ == "__main__":
	resp = sendRequest('/rsServiceControl/getOwnServices')
	for service in resp['info']['mServiceList']:
		name = service["value"]["mServiceName"]
		id = service["key"]

		req = {'serviceId': id}
		resp = sendRequest('/rsServiceControl/getServicePermissions', req)
		if not resp['retval']:
			continue

		p = resp['permissions']
		p['mDefaultAllowed'] = True
		p['mPeersDenied'].clear()
		p['mPeersAllowed'].clear()

		# update req
		req['permissions'] = p
		sendRequest('/rsServiceControl/updateServicePermissions', req)
