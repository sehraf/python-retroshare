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


# curl -u 'test:tset' --data '{"mId":"rsMsgs/getMessage"}' --silent http://127.0.0.1:9092/rsServiceControl/getOwnServices | grep mServiceName | sed -e 's/mServiceName":\s"//g' -e 's/"/'"'"'/g' -e 's/,/: False,/g' -e 's/\s\s//g'
# 'disc': False,
# 'chat': False,
# 'msg': False,
# 'turtle': False,
# 'heartbeat': False,
# 'ft': False,
# 'Global Router': False,
# 'file_database': False,
# 'serviceinfo': False,
# 'bandwidth_ctrl': False,
# 'GxsTunnels': False,
# 'banlist': False,
# 'status': False,
# 'gxsid': False,
# 'gxsforums': False,
# 'gxsposted': False,
# 'gxschannels': False,
# 'gxscircle': False,
# 'gxsreputation': False,
# 'GXS Mails': False,
# 'rtt': False,

presets = {
	'Graveyard': {
		# we only need discovery to easily bootstrap a long offline node
		'disc': True,
		'chat': False,
		'msg': False,
		'turtle': False,
		'heartbeat': False,
		'ft': False,
		'Global Router': False,
		'file_database': False,
		'serviceinfo': False,
		'bandwidth_ctrl': False,
		'GxsTunnels': False,
		'banlist': False,
		'status': False,
		'gxsid': False,
		'gxsforums': False,
		'gxsposted': False,
		'gxschannels': False,
		'gxscircle': False,
		'gxsreputation': False,
		'GXS Mails': False,
		'rtt': False,
	},
	'hidden': {
		# turn off some services
		'disc': False,
		# 'chat': True,
		# 'msg': True,
		# 'turtle': False,
		'heartbeat': False,
		# 'ft': True,
		'Global Router': False,
		# 'file_database': True,
		# 'serviceinfo': True,
		# 'bandwidth_ctrl': True,
		# 'GxsTunnels': True,
		# 'banlist': True,
		# 'status': True,
		# 'gxsid': True,
		# 'gxsforums': True,
		# 'gxsposted': True,
		# 'gxschannels': True,
		# 'gxscircle': True,
		# 'gxsreputation': True,
		# 'GXS Mails': True,
		'rtt': False,
	}
}

def matchGraveyard(val):
	if not val:
		return False
	return val == 'Graveyard'

def matchHidden(val):
	if not val:
		return False
	return re.search('.+\.onion$|.+\.b32\.i2p$', val) is not None

def matchName(val):
	if not val:
		return False
	return re.search('.*test.*', val) is not None

rules = [
	{
		# group: match group name
		'type': 'group',
		'criterion': matchGraveyard,
		'perms': presets['Graveyard']
	},
	{
		# address: match address
		# tries to match connected address or latest tracked
		'type': 'address',
		'criterion': matchHidden,
		'perms': presets['hidden']
	},
	{
		# match (pgp) peer name
		'type': 'name',
		'criterion': matchName,
		'perms': {
			'turtle': False,
		}
	}
]


class rsServicePerms:
	def __init__(self):
		self.names = {}
		self.services = {}

		resp = sendRequest('/rsServiceControl/getOwnServices')
		for service in resp['info']['mServiceList']:
			name = service["value"]["mServiceName"]
			id = service["key"]

			self.services[id] = service["value"]
			self.names[name] = id

	def getId(self, name):
		if name in self.names:
			return self.names[name]
		else:
			return -1

	def setPerms(self, perms, sslId):
		print('setting perms for ' + sslId)
		# print(perms)
		for name, allowed in perms.items():
			# get perm from RS
			req = {'serviceId': self.getId(name)}
			resp = sendRequest('/rsServiceControl/getServicePermissions', req)
			if not resp['retval']:
				continue
			p = resp['permissions']

			if p['mDefaultAllowed']:
				# manage blacklist
				if allowed:
					if sslId in p['mPeersDenied']:
						p['mPeersDenied'].remove(sslId)
				else:
					p['mPeersDenied'].append(sslId)
			else:
				# manage whitelist
				if allowed:
					p['mPeersAllowed'].append(sslId)
				else:
					if sslId in p['mPeersAllowed']:
						p['mPeersAllowed'].remove(sslId)
					
			# update req
			req['permissions'] = p
			sendRequest('/rsServiceControl/updateServicePermissions', req)



if __name__ == "__main__":
	perms = rsServicePerms()
	peers = sendRequest('/rsPeers/getFriendList')['sslIds']
	groups = sendRequest('/rsPeers/getGroupInfoList')['groupInfoList']

	# cache details
	details = {}
	for peer in peers:
		# get details
		req = {'sslId': peer}
		resp = sendRequest('/rsPeers/getPeerDetails', req)
		if not resp['retval']:
			continue
		details[peer] = resp['det']

	# go through rules
	for rule in rules:
		# ##################################################
		# groups
		# ##################################################
		if   rule['type'] is 'group':
			# find matching group
			for group in groups:
				if rule['criterion'](group['name']):
					print('found matching group ' + group['name'])
					peerIds = group['peerIds']
	
					if not peerIds:
						continue

					# we have a list of peers that match a group for the current rule
					# now apply permissions
					print('got ' + str(len(peerIds)) + ' pgpIds')
					for peer in peerIds:						
						# get sslIds
						for id, d in details.items():
							if d['gpg_id'] == peer:
								perms.setPerms(rule['perms'], id)

		# ##################################################
		# address
		# ##################################################
		elif rule['type'] is 'address':			

			for peer in peers:
				d = details[peer]
				# check for connected address or latest on record
				match = False
				if d['isHiddenNode']:
					match = match or rule['criterion'](d['hiddenNodeAddress'])
				else:
					match = match or rule['criterion'](d['connectAddr'])
					match = match or (d['ipAddressList'] and rule['criterion'](d['ipAddressList'][0]))

				if not match: 
					continue
				print('found matching address ' + d['name'] + '/' + d['location'])
				perms.setPerms(rule['perms'], peer)

		# ##################################################
		# name
		# ##################################################
		elif rule['type'] is 'name':			

			for peer in peers:
				d = details[peer]

				if not rule['criterion'](d['name']): 
					continue
				print('found matching name ' + d['name'] + '/' + d['location'])
				perms.setPerms(rule['perms'], peer)
