#!/usr/bin/env python3

import json, requests, time, math

debug = False

port = 9092
user = 'test'
pw = 'tset'
groupName = "Graveyard"
offlineLimit = 30 # days


def debugDump(label, data):
	if not debug: return
	print(label, json.dumps(data, sort_keys=True, indent=4))

def sendRequest(function, data = None):
	url = 'http://127.0.0.1:' + str(port) + function

	debugDump('POST: ' + url, data)
	resp = requests.post(url=url, json=data, auth=(user, pw))

	debugDump('RESP', resp.json())
	return resp.json()

class rsGroup:
	def __init__(self, name):
		self.name = name
		self.info = {}

		# init info
		req = {'groupName': name}
		resp = sendRequest('/rsPeers/getGroupInfoByName', req)

		if resp['retval']:
			self.info = resp['groupInfo']
		else:
			create()

	def create(self):
		self.info = {
				'name': self.name,
				'id': 0,
				'flag': 0,
				'peerIds': []
			}

		req = {'groupInfo': self.info}
		# assume no error here
		sendRequest('/rsPeers/addGroup', req)

		req = {'groupName': self.name}
		self.info = sendRequest('/rsPeers/getGroupInfoByName', req)['groupInfo']

	def delete(self):
		req = {'groupInfo': self.info}
		sendRequest('/rsPeers/removeGroup', req)
		self.info = {}

	def addPeer(self, peer):
		self.assignPeer(peer, True)

	def removePeer(self, peer):
		self.assignPeer(peer, False)

	def addPeers(self, peers):
		self.assignPeers(peers, True)

	def removePeers(self, peers):
		self.assignPeers(peers, False)

	def assignPeer(self, peer, assign):
		req = {
				'groupId': self.info['id'], 
				'peerId': peer,
				'assign': assign
			}
		resp = sendRequest('/rsPeers/assignPeerToGroup', req)
		if resp['retval']:
			if assign:
				self.info['peerIds'].append(peer)
			else:
				self.info['peerIds'].remove(peer)

	def assignPeers(self, peers, assign):
		req = {
				'groupId': self.info['id'], 
				'peerIds': peers,
				'assign': assign
			}
		resp = sendRequest('/rsPeers/assignPeersToGroup', req)

	def isAssigned(self, pgpId):
		return pgpId in self.info['peerIds']

	def update(self):
		req = {'groupName': self.name}
		self.info = sendRequest('/rsPeers/getGroupInfoByName', req)['groupInfo']

def getDays(details):
	days = time.time() - details['lastConnect']
	days = days / 3600 / 24
	days = math.ceil(days)
	return days

if __name__ == "__main__":
	group   = rsGroup(groupName)
	friends = sendRequest('/rsPeers/getFriendList')['sslIds']

	# we go though the list of locations
	# -> we can have one friend with long time offline locations and recent locations
	# -> first move to group then remove
	toAdd = []
	toRemove = []
	names = {}
	days = {}

	# add long offline friends
	for friend in friends:
		req = {'sslId': friend}
		details = sendRequest('/rsPeers/getPeerDetails', req)['det']
		pgpId = details['gpg_id']

		d = getDays(details)

		if d > offlineLimit:
			if not pgpId in toAdd:
				toAdd.append(pgpId)
				names[pgpId] = details["name"]
				days[pgpId] = d

	# remove recent online friends
	for friend in friends:
		req = {'sslId': friend}
		details = sendRequest('/rsPeers/getPeerDetails', req)['det']
		pgpId = details['gpg_id']

		d = getDays(details)

		if d < offlineLimit:
			if pgpId in toAdd:
				toAdd.remove(pgpId)
			if group.isAssigned(pgpId):
				toRemove.append(pgpId)
				names[pgpId] = details["name"]
				days[pgpId] = d

	# ensure we have an updated peer list
	group.update()

	# toAdd now contains only the peers that are too long offline (excluding those with one recent online and one too long offline location)
	for pgpId in toAdd:
		if not group.isAssigned(pgpId):
			print("burrying " + names[pgpId] + "\t(offline for " + str(days[pgpId]) + " days)")
		else:
			toAdd.remove(pgpId)
	group.addPeers(toAdd)

	# ensure we have an updated peer list
	group.update()

	for pgpId in toRemove:
		if group.isAssigned(pgpId):
			print("unearthing " + names[pgpId] + "\t(offline for " + str(days[pgpId]) + " days)")
		else:
			toRemove.remove(pgpId)
	group.removePeers(toRemove)

