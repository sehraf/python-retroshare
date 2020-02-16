#!/usr/bin/env python3

import json, requests, re
from git import Repo

debug = False

port = 9092
user = 'test'
pw = 'tset'
repoPath = '~/Projects/RetroShare'

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


if __name__ == "__main__":
	repo = rsGit()

	friends = sendRequest('/rsPeers/getFriendList')['sslIds']
	gits = {}
	versions = {}
	versionUnknown = []
	entries = 0

	for friend in friends:
		req = {'id': friend}
		resp = sendRequest('/rsGossipDiscovery/getPeerVersion', req)

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
				versionUnknown.append(versionStr)
				continue
			version = match.group(1)
			if match.group(3)[0] == 'g':
				git = match.group(3)[1:]
			else:
				# 0.6.9999-208-g62ab99fc4-OBS
				if match.group(2)[0] == 'g':
					git = match.group(2)[1:]
				else:
					versionUnknown.append(versionStr)
					continue
		else:
			version = match.group(1)
			git = match.group(2)

		# some sanuity checks
		#print(version, git)
		if len(git) < 5:
			#print('git hash too short', git)
			versionUnknown.append(versionStr)
			continue
		try:
			# this is supposed to be a hexadecimal string
			int('0x' + git, 16)
		except ValueError:
			#print('invalid git hash', git)
			versionUnknown.append(versionStr)
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
	print('---------------------------------')

	# just sort by string, will follow RS's numbering scheme
	for version, number in sorted(versions.items(), key=lambda x: x[0]):
		print(version + ':\t' + ('\t' if len(version) < 9 else '') + 'times seen: ' + str(number))
	print('---------------------------------')

	# sort approximately to publish/commit date
	sorter = lambda x: (x.valid, x.tagIsLatest, int(x.rev) if x.valid else -1)
	for d in sorted(dataSet, key=sorter):
		# get data
		hash, tag, tagLatest, rev, valid, number = d.getData()

		while len(hash) < 9:
			hash = hash + ' '

		if valid:
			print(hash + ':  rev: ' + rev + '\ttimes seen: ' + str(number) + ('' if tagLatest else '\t(' + tag + ')'))
		else:
			print(hash + ':  ~invalid~\ttimes seen: ' + str(number))

		if hash == '01234567 ':
			future = future + number
			continue

		if not valid:
			continue
			
		if tagLatest:
			future = future + number
		else: 
			past = past + number
	print('---------------------------------')

	print('older than last release:         ' + str(past))
	print('newer than / equal last release: ' + str(future))
	print('(excluding invalids, counting "01234567" as newer)')
	print('---------------------------------')

	print('The following version strings are not understand:')
	for v in versionUnknown:
		print(v)
