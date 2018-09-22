#!/usr/bin/env python3

import json, requests, html
from subprocess import check_output

debug = False

port = 9092
user = 'test'
pw = 'tset'
lobbyName = 'Retroshare Devel (signed)'
# lobbyName = 'abcdefg'
program = './ipOverview.py'

def debugDump(label, data):
	if not debug: return
	print(label, json.dumps(data, sort_keys=True, indent=4))

def sendRequest(function, data = None):
	url = 'http://127.0.0.1:' + str(port) + function

	debugDump('POST: ' + url, data)
	resp = requests.post(url=url, json=data, auth=(user, pw))

	debugDump('RESP', resp.json())
	return resp.json()

class rsChat:
	def __init__(self, name):
		self.id = 0
		self.info = None

		idList = sendRequest('/rsMsgs/getChatLobbyList')['cl_list']
		for chatLobbyId in idList:
			req = {'id': int(chatLobbyId)}
			resp = sendRequest('/rsMsgs/getChatLobbyInfo', req)

			if not resp['retval']:
				continue

			info = resp['info']
			# print(info['lobby_name'])

			if info['lobby_name'] == name:
				self.id = int(chatLobbyId)
				self.info = info

				break

	def send(self, msg):
		if self.id == 0:
			return

		req = {
				'id': {
					# 'broadcast_status_peer_id' : '0' * 32,
					'type': 3, # chat lobby
					# 'peer_id': '0' * 32,
					# 'distant_chat_id': '0' * 32,
					'lobby_id': self.id
				},
				'msg': msg
			}
		sendRequest('/rsMsgs/sendChat', req)

	def htmlify(self, msg):
		# msg.replace('\t', '&nbsp;' * 8)
		return html.escape(msg)
		# return msg

if __name__ == "__main__":
	chat = rsChat(lobbyName)
	output = check_output([program])
	output = output.decode("utf-8") 

	# print(output)

	output = '[sending from python]:\n' + output
	chat.send(output)
