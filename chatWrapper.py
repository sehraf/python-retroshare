#!/usr/bin/env python3

import json, requests, html, argparse
from subprocess import check_output

debug = False

lobbyName = 'Retroshare Devel (signed)'
# lobbyName = 'abcdefg'
# lobbyName = 'testChat'
# program = './ipOverview.py'
program = './discOverview.py'

def debugDump(label, data):
	if not debug: return
	print(label, json.dumps(data, sort_keys=True, indent=4))


class rsHost:
	_ip = '127.0.0.1'
	_port = '9092'
	_auth = ('test', 'tset')

	def __init__(self):
		parser = argparse.ArgumentParser(description='reads standard RS json API parameters.')
		parser.add_argument('--port', '-p', dest='port')
		parser.add_argument('--addr', '-a', dest='addr')
		parser.add_argument('--user', '-u', dest='user')
		parser.add_argument('--pass', '-P', dest='pw')
		args = parser.parse_args()

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


class rsChat:
	def __init__(self, rs, name):
		self.id = 0
		self.info = None
		self.rs = rs

		idList = self.rs.sendRequest('/rsMsgs/getChatLobbyList')['cl_list']
		for chatLobbyId in idList:
			req = {'id': int(chatLobbyId)}
			resp = self.rs.sendRequest('/rsMsgs/getChatLobbyInfo', req)

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
		self.rs.sendRequest('/rsMsgs/sendChat', req)

	def htmlify(self, msg):
		# msg.replace('\t', '&nbsp;' * 8)
		return html.escape(msg)
		# return msg

if __name__ == "__main__":
	rs = rsHost()
	chat = rsChat(rs, lobbyName)
	output = check_output([program])
	output = output.decode("utf-8") 

	# print(output)

	output = '[sending from python]:\n' + output
	chat.send(output)
