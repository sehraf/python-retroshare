#!/usr/bin/env python3

import json, requests, re, argparse
from git import Repo

debug = False

repoPath = '~/Projects/RetroShare'

def debugDump(label, data):
	if not debug: return
	print(label, json.dumps(data, sort_keys=True, indent=4))

class rsHost:
	_ip = '127.0.0.1'
	_port = '9092'
	_auth = ('test', 'tset')

	def __init__(self):
		parser = argparse.ArgumentParser(description='reads standard RS json API parameters.')
		parser.add_argument('--port', '-p', help='json api port')
		parser.add_argument('--addr', '-a', help='json api address')
		parser.add_argument('--user', '-u', help='json api user')
		parser.add_argument('--pass', '-P', help='json api password', dest='pw')
		args, _ = parser.parse_known_args()

		# print(args)

		if args.addr is not None:
			self._ip = args.addr
		if args.port is not None:
			self._port = args.port
		if args.user is not None and args.pw is not None:
			self._auth = (args.user, args.pw)

		pass

	def sendRequest(self, function, data=None):
		url = 'http://' + self._ip + ':' + self._port + function

		debugDump('POST: ' + url, data)
		resp = requests.post(url=url, json=data, auth=self._auth)

		# gracefully add 401 error
		if resp.status_code == 401:
			return {'retval': False}

		debugDump('RESP', resp.json())
		return resp.json()


class dataStruct:
	def __init__(self, gitHash: str, tag: str, tagIsLatest: bool, rev: int, valid: bool, number: int):
		self.gitHash = gitHash
		self.tag = tag
		self.tagIsLatest = tagIsLatest
		self.rev = rev
		self.valid = valid
		self.number = number

	def getData(self) -> tuple:
		return (self.gitHash, self.tag, self.tagIsLatest, self.rev, self.valid, self.number)



class rsGit:
	# v0.6.4-481-gfe5e83125
	regEx = '(.+-?.+)-(.+)-(.+)'
	def __init__(self):
		self.git = Repo(repoPath)
		#self.git.git.checkout('RetroShare/master')

		t = self.git.git.describe('--tags')
		match = re.search(self.regEx, t)

		if match is not None:
			self.tag = match.group(1)
		else:
			# v0.6.5-RC1
			self.tag = t

	def getCommitNum(self, hash: str):
		try:
			t = self.git.git.describe('--tags', hash)
		except:
			return False, False, '', ''
		match = re.search(self.regEx, t)
		if match == None:
			return False, False, '', ''

		# get number of commits		
		num = match.group(2)

		# get last tag
		tag = match.group(1)

		return True, tag == self.tag, tag, num


def addUnknown(data, entry):
	if entry in data:
		data[entry] += 1
	else:
		data[entry] = 1

def line():
	print('-' * 50)


if __name__ == "__main__":
	rs = rsHost()
	repo = rsGit()

	friends = rs.sendRequest('/rsPeers/getFriendList')['sslIds']
	gits = {}
	versions = {}
	versionUnknown = {}
	entries = 0

	for friend in friends:
		req = {'id': friend}
		resp = rs.sendRequest('/rsGossipDiscovery/getPeerVersion', req)

		if not resp['retval']:
			continue
		versionStr = resp['version']
		#print(versionStr)

		# 0.6.4 Revision 90393419
		match = re.search('(.*)\sRevision\s([a-f0-9]+)', versionStr)
		if match == None:
			# 0.6.4-524-gb51b1fc8c
			match = re.search(rsGit.regEx, versionStr)
			if match == None:
				addUnknown(versionUnknown, versionStr)
				continue
			version = match.group(1)
			if match.group(3)[0] == 'g':
				git = match.group(3)[1:]
			else:
				# 0.6.9999-208-g62ab99fc4-OBS
				if match.group(2)[0] == 'g':
					git = match.group(2)[1:]
				else:
					addUnknown(versionUnknown, versionStr)
					continue
		else:
			version = match.group(1)
			git = match.group(2)

		# some sanuity checks
		#print(version, git)
		if len(git) < 5:
			#print('git hash too short', git)
			addUnknown(versionUnknown, versionStr)
			continue
		try:
			# this is supposed to be a hexadecimal string
			int('0x' + git, 16)
		except ValueError:
			#print('invalid git hash', git)
			addUnknown(versionUnknown, versionStr)
			continue
		
		if version in versions:
			versions[version] = versions[version] + 1			
		else:
			versions[version] = 1

		if git in gits:
			gits[git] = gits[git] + 1
		else:
			gits[git] = 1

		entries = entries + 1


	past = 0
	future  = 0
	# collect information from git (for later sorting)
	dataSet = []
	for hash, number in gits.items():
		valid, tagLatest, tag, rev = repo.getCommitNum(hash)
		dataSet.append(dataStruct(hash, tag, tagLatest, rev, valid, number))
	#print([x.getData() for x in dataSet])

	# old sorting
	# for hash, number in sorted(gits.items(), key=lambda x: x[1]):
	# 	valid, tagLatest, tag, rev = repo.getCommitNum(hash)

	print('found ' + str(entries) + ' entries')
	line()

	# just sort by string, will follow RS's numbering scheme
	for version, number in sorted(versions.items(), key=lambda x: x[0]):
		print('{:24}times seen: {}'.format(version, number))
	line()

	# sort approximately to publish/commit date
	sorter = lambda x: (x.valid, x.tagIsLatest, x.tag ,int(x.rev) if x.valid else -1)
	for d in sorted(dataSet, key=sorter):
		# get data
		hash, tag, tagLatest, rev, valid, number = d.getData()

		print('{:12}{:12}times seen: {!s:3} {}'.format(hash, (('rev: ' + rev) if valid else '~invalid~'), number, ('' if tagLatest or not valid else ('(' + tag + ')'))))

		# count how many are newer/older than the latest (official release)
		if '01234567' in hash:
			future = future + number
			continue

		if not valid:
			continue
			
		if tagLatest:
			future = future + number
		else: 
			past = past + number
	line()

	print('older than last release:         ' + str(past))
	print('newer than / equal last release: ' + str(future))
	print('(excluding invalids, counting "01234567" as newer)')
	line()

	print('The following version strings are not understand:')
	for v in versionUnknown:
		print('{:12} time(s) {!s}'.format(versionUnknown[v], v))
