#!/usr/bin/env python3

import json, requests, re

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

	# TCP/UDP
	tcpi = 0
	tcpo = 0
	udpi = 0
	udpo = 0

	for friend in friends:
		req = {'sslId': friend}
		details = sendRequest('/rsPeers/getPeerDetails', req)['det']

		ser = 1 if details['actAsServer'] else 0

		if details['isHiddenNode']:
			con = 0 if details['connectAddr'] == "" else 1

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
			if re.search('^\d+.\d+.\d+.\d+$', details['connectAddr']) != None:
				v4c = v4c + 1
				v4o = v4o + (1 - ser)
				v4i = v4i + ser
			else:
				v6c = v6c + 1
				v6o = v6o + (1 - ser)
				v6i = v6i + ser

		# count TCP/UDP
		# /* Connect state */
		# const uint32_t RS_PEER_CONNECTSTATE_OFFLINE           = 0;
		# const uint32_t RS_PEER_CONNECTSTATE_TRYING_TCP        = 2;
		# const uint32_t RS_PEER_CONNECTSTATE_TRYING_UDP        = 3;
		# const uint32_t RS_PEER_CONNECTSTATE_CONNECTED_TCP     = 4;
		# const uint32_t RS_PEER_CONNECTSTATE_CONNECTED_UDP     = 5;
		# const uint32_t RS_PEER_CONNECTSTATE_CONNECTED_TOR     = 6;
		# const uint32_t RS_PEER_CONNECTSTATE_CONNECTED_I2P     = 7;
		# const uint32_t RS_PEER_CONNECTSTATE_CONNECTED_UNKNOWN = 8;
		v = details['connectState']
		if v is 4:
			tcpo = tcpo + (1 - ser)
			tcpi = tcpi + ser
		elif v is 5:
			udpo = udpo + (1 - ser)
			udpi = udpi + ser

	print('Connection statistics:')
	print('IPv4: ' + str(v4) + '  \t(connected: ' + str(v4c) + '\tin: ' + str(v4i) + '\tout: ' + str(v4o) + ' )')
	print('IPv6: ' + str(v6) + '  \t(connected: ' + str(v6c) + '\tin: ' + str(v6i) + '\tout: ' + str(v6o) + ' )')
	print('')
	print('Hidden services:')
	print('Tor:  ' + str(t)  + '  \t(connected: ' + str(tc) + '\tin: ' + str(ti) + '\tout: ' + str(to) + ' )')
	print('I2P:  ' + str(i)  + '  \t(connected: ' + str(ic) + '\tin: ' + str(ii) + '\tout: ' + str(io) + ' )')
	print('')
	print('TCP/UDP (excluding Tor/I2P):')
	print('TCP:  ' + str(tcpi + tcpo)  + '  \t(in: ' + str(tcpi) + '\tout: ' + str(tcpo) + ' )')
	print('UDP:  ' + str(udpi + udpo)  + '  \t(in: ' + str(udpi) + '\tout: ' + str(udpo) + ' )')