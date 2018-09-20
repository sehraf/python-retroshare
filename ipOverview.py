#!/usr/bin/env python3

import json, requests, re

debug = False

port = 9092

def debugDump(label, data):
	if not debug: return
	print(label, json.dumps(data, sort_keys=True, indent=4))

def sendRequest(function, data = None):
	url = 'http://127.0.0.1:' + str(port) + function

	debugDump('POST: ' + url, data)
	resp = requests.post(url=url, json=data)

	debugDump('RESP', resp.json())
	return resp.json()

if __name__ == "__main__":
	friends = sendRequest('/rsPeers/getFriendList')['sslIds']

	# IPv4
	v4 = 0
	v4c = 0
	v4i = 0
	v4o = 0

	# IPv6
	v6 = 0
	v6c = 0
	v6i = 0
	v6o = 0

	# Tor
	t = 0
	tc = 0
	ti = 0
	to = 0

	# I2P
	i = 0
	ic = 0
	ii = 0
	io = 0

	for friend in friends:
		req = {'sslId': friend}
		details = sendRequest('/rsPeers/getPeerDetails', req)['det']

		if details['isHiddenNode']:
			con = 0 if details['connectAddr'] == "" else 1
			ser = 1 if details['actAsServer'] else 0

			# count peers
			if details['hiddenNodeAddress'].endswith('.onion'):
				t = t + 1
				tc = tc + con

			else:
				i = i + 1
				ic = ic + con

			if con == 0:
				continue

			# count online
			if details['hiddenNodeAddress'].endswith('.onion'):
				to = to + (1 - ser)
				ti = ti + ser
			else:
				io = io + (1 - ser)
				ii = ii + ser
		else:
			# count IPs
			ips = details['ipAddressList']
			for ip in ips:
				if ip[3] == '4':
					v4 = v4 + 1			
				else:
					v6 = v6 + 1

			if details['connectAddr'] == "":
				continue
			
			# count online
			ser = 1 if details['actAsServer'] else 0
			if re.search('^\d+.\d+.\d+.\d+$', details['connectAddr']) != None:
				v4c = v4c + 1
				v4o = v4o + (1 - ser)
				v4i = v4i + ser
			else:
				v6c = v6c + 1
				v6o = v6o + (1 - ser)
				v6i = v6i + ser

	print('IPv4: ' + str(v4) + '  \t(connected: ' + str(v4c) + '\tin: ' + str(v4i) + '\tout: ' + str(v4o) + ' )')
	print('IPv6: ' + str(v6) + '  \t(connected: ' + str(v6c) + '\tin: ' + str(v6i) + '\tout: ' + str(v6o) + ' )')
	# print('IPv4: ' + str(v4))
	# print('IPv6: ' + str(v6))
	print('Tor:  ' + str(t)  + '  \t(connected: ' + str(tc) + '\tin: ' + str(ti) + '\tout: ' + str(to) + ' )')
	print('I2P:  ' + str(i)  + '  \t(connected: ' + str(ic) + '\tin: ' + str(ii) + '\tout: ' + str(io) + ' )')