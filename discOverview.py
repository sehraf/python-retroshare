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

class rsGit:
	# v0.6.4-481-gfe5e83125
	regEx = '(.+-?.+)-(.+)-(.+)'
	def __init__(self):
		self.git = Repo(repoPath)
		self.git.git.checkout('RetroShare/master')

		t = self.git.git.describe('--tags')
		match = re.search(self.regEx, t)

		if match is not None:
			self.tag = match.group(1)
		else:
			# v0.6.5-RC1
			self.tag = t

	def getCommitNum(self, hash):
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
	entries = 0

	for friend in friends:
		req = {'id': friend}
		resp = sendRequest('/rsDisc/getPeerVersion', req)

		if not resp['retval']:
			continue
		versionStr = resp['versions']
		
		# 0.6.4 Revision 90393419
		match = re.search('(.*)\sRevision\s([a-f0-9]+)', versionStr)
		if match == None:
			# 0.6.4-524-gb51b1fc8c
			match = re.search(rsGit.regEx, versionStr)
			if match == None:
				continue
			version = match.group(1)
			git = match.group(3)[1:]
		else:
			version = match.group(1)
			git = match.group(2)

		# print(version, git)
		
		if version in versions:
			versions[version] = versions[version] + 1			
		else:
			versions[version] = 1

		if git in gits:
			gits[git] = gits[git] + 1
		else:
			gits[git] = 1

		entries = entries + 1

	print('found ' + str(entries) + ' entries')
	print('---------------------------------')

	for version, number in sorted(versions.items(), key=lambda x: x[0]):
		print(version + ':\ttimes seen: ' + str(number))
	print('---------------------------------')

	past = 0
	future  = 0
	for hash, number in sorted(gits.items(), key=lambda x: x[1]):
		valid, tagLatest, tag, rev = repo.getCommitNum(hash)

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