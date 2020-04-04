#!/usr/bin/env python3

import json, requests, html, argparse, re, html2text, random
from enum import IntEnum
from typing import Union
# import signal
# import sys

debug = False

# shouldStop = False

# lobbyName = 'Retroshare Devel (signed)'
# lobbyName = 'abcdefg'
# lobbyName = 'test'

lobbies_to_auto_join = [
	'Retroshare Devel (signed)'
]


def debugDump(label, data):
	if not debug: return
	print(label, json.dumps(data, sort_keys=True, indent=4))


class rsHost:
	# some defaults
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

		self._baseUrl = 'http://' + self._ip + ':' + self._port + '/'

	def sendRequest(self, function, data=None):
		if function[0] == '/': function = function[1:]
		url = self._baseUrl + function

		debugDump('POST: ' + url, data)
		resp = requests.post(url=url, json=data, auth=self._auth)

		# gracefully add 401 error
		if resp.status_code == 401:
			return {'retval': False}

		debugDump('RESP', resp.json())
		return resp.json()

	def getEventsStream(self, eventType: int = 0):
		from sseclient import SSEClient
		for mRecord in SSEClient(
				self._baseUrl + "/rsEvents/registerEventsHandler",
				auth=self._auth,
				json={"eventType": eventType}):
			try:
				mEvent = json.loads(mRecord.data)["event"]
				## Older RetroShare version doesn't filter events type
				if (mEvent["mType"] == eventType or eventType == 0):
					yield mEvent
			except(KeyError):
				if json.loads(mRecord.data)["retval"]:
					continue
			except(TypeError):
				print(mRecord)
				print("Got invalid record:", mRecord.dump().encode("utf8"))


class rsChatType(IntEnum):
	TYPE_NOT_SET = 0
	TYPE_PRIVATE = 1
	TYPE_PRIVATE_DISTANT = 2
	TYPE_LOBBY = 3
	TYPE_BROADCAST = 4

	@classmethod
	def valid(cls, pattern: int):
		return any(pattern == item.value for item in cls)


class rsChat:
	def __init__(self, rs: rsHost, name: Union[str, None] = None):
		self.id = -1
		self.info = None
		self.rs = rs

		if name is None:
			return

		# fetch chat info
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

	def send(self, msg: str, chat_id: Union[dict, None]):
		req = {
			'id': {},
			'msg': msg
		}

		if self.id == -1:
			# no info set expect chat_id!
			if chat_id is None:
				# fail
				return
			req['id'] = chat_id
		else:
			req['id']['type'] = 3
			req['id']['lobby_id'] = self.id

		self.rs.sendRequest('/rsMsgs/sendChat', req)

	def htmlify(self, msg: str) -> str:
		# msg.replace('\t', '&nbsp;' * 8)
		return html.escape(msg)

	# return msg

	def isOK(self) -> bool:
		return self.id != -1


class rsBotRule:
	def __init__(self, name: str, enabled: bool, response: str, matches: list):
		self.name = name

		self.enabled = enabled

		self.response = response
		self.matches = matches

	def triggered(self, txt: str) -> Union[bool, tuple]:
		if not self.enabled:
			return False

		for m in self.matches:
			result = m.match(txt)
			# print(m, txt, result)
			if result is not None:
				return True, result.groups

		return False


class rsBot:
	def __init__(self, rs: rsHost, chat: rsChat):
		self.chat = chat
		self.rs = rs
		self.rules = []

	def run(self):
		for event in rs.getEventsStream(15):
			# print(event)
			self._process_event(event['mChatMessage'])

	def add_rule(self, rule: rsBotRule):
		self.rules.append(rule)

	def _get_peer_name(self, peer_id: str) -> str:
		req = {'sslId': peer_id}
		details = rs.sendRequest('rsPeers/getPeerDetails', req)['det']
		return details['name']

	def _get_gxs_id_name(self, gxs_id: str) -> str:
		req = {'id': gxs_id}
		details = rs.sendRequest('rsIdentity/getIdDetails', req)['details']
		return details['mNickname']

	def _get_distant_peer_name(self, distant_id: str) -> str:
		req = {'pid': distant_id}
		info = rs.sendRequest('rsMsgs/getDistantChatStatus', req)['info']
		to_id = info['to_id']
		return self._get_gxs_id_name(to_id)

	def _get_lobby_name(self, lobby_id: int) -> str:
		req = {'id': lobby_id}
		info = self.rs.sendRequest('/rsMsgs/getChatLobbyInfo', req)['info']
		return info['lobby_name']

	def _process_event(self, msg):
		# print(msg)

		# get chat id / source
		type = msg['chat_id']['type']
		if not rsChatType.valid(type):
			# invalid, ignore
			return

		if type == rsChatType.TYPE_BROADCAST:
			self._process_broadcast(msg)
		elif type == rsChatType.TYPE_LOBBY:
			self._process_lobby(msg)
		elif type == rsChatType.TYPE_PRIVATE:
			self._process_private(msg)
		elif type == rsChatType.TYPE_PRIVATE_DISTANT:
			self._process_private_distant(msg)

	def _process_broadcast(self, msg):
		source_peer_id = msg['broadcast_peer_id']
		source_peer_name = self._get_peer_name(source_peer_id)

		# print('received brodcast message')
		# print('from', source_peer_name)
		# print('msg ', msg['msg'])

		self._process_message(msg, source_peer_name)

	def _process_lobby(self, msg):
		source_lobby_id = msg['chat_id']['lobby_id']
		source_lobby_name = self._get_lobby_name(source_lobby_id)

		source_peer_id = msg['lobby_peer_gxs_id']
		source_peer_name = self._get_gxs_id_name(source_peer_id)

		# print('received chat lobby message')
		# print('in  ', source_lobby_name)
		# print('from', source_peer_name)
		# print('msg ', msg['msg'])

		self._process_message(msg, source_peer_name, source_lobby_name)

	def _process_private(self, msg):
		source_peer_id = msg['chat_id']['peer_id']
		source_peer_name = self._get_peer_name(source_peer_id)

		# print('received private message')
		# print('from', source_peer_name)
		# print('msg ', msg['msg'])

		self._process_message(msg, source_peer_name)

	def _process_private_distant(self, msg):
		source_peer_id = msg['chat_id']['distant_chat_id']
		source_peer_name = self._get_distant_peer_name(source_peer_id)

		# print('received distant chat message')
		# print('from', source_peer_name, source_peer_id)
		# print('msg ', msg['msg'])

		self._process_message(msg, source_peer_name)

	def _process_message(self, chat_message: json, sender_name: str, lobby_name: Union[str, None] = None):
		# get the plain text message
		h = html2text.HTML2Text()
		# todo add more usefull options here
		h.ignore_links = True
		txt = h.handle(chat_message['msg'])
		txt = txt.rstrip()

		for rule in self.rules:
			triggered = rule.triggered(txt)
			if triggered is False:
				continue
			print(triggered)
			groups = triggered[1]
			print(rule.name, 'triggered')

			response = rule.response
			response = response.replace('$$nick', sender_name)
			response = response.replace('$$message', txt)

			for i in range(len(groups())):
				response = response.replace('$$match_' + str(i + 1), groups()[i])

			self.chat.send(response, chat_message['chat_id'])

		# special rules
		if re.match('^!rules$', txt, re.IGNORECASE) is not None or \
				re.match('^!commands$', txt, re.IGNORECASE) is not None:
			response = ''
			response += '!rtd (<max>)' + ', '
			for r in self.rules:
				response += r.name + ', '
			response = response[:-2]
			self.chat.send(response, chat_message['chat_id'])
		match = re.match('^!rtd\s*(\d*)$', txt, re.IGNORECASE)
		if match is not None:
			max = 6
			if match.group(1) is not None:
				try:
					max = int(match.group(1))
				except ValueError:
					pass
			rng = random.randrange(max)
			response = 'rolling a d' + str(max) + ': ' + str(rng)
			self.chat.send(response, chat_message['chat_id'])
	# if re.match('^!commands$', txt, re.IGNORECASE) is not None:
	# 	response = '!info, !commands, !help'
	# 	self.chat.send(response, chat_message['chat_id'])


if __name__ == "__main__":
	# def signal_handler(sig, frame):
	# 	global shouldStop
	# 	print('You pressed Ctrl+C!')
	#
	# 	shouldStop = True
	# 	sys.exit(0)

	# signal.signal(signal.SIGINT, signal_handler)

	rs = rsHost()
	chat = rsChat(rs)

	bot = rsBot(rs, chat)
	# ping, pong, test
	bot.add_rule(rsBotRule('ping', True, 'pong', [re.compile('^ping$', re.IGNORECASE)]))
	bot.add_rule(rsBotRule('pong', True, 'pong²', [re.compile('^pong$', re.IGNORECASE)]))
	bot.add_rule(rsBotRule('test', True, '@$$nick: test back', [re.compile('^test$', re.IGNORECASE)]))

	# info, help
	bot.add_rule(rsBotRule('info', True, 'I\'m just a python script!', [re.compile('^!info$', re.IGNORECASE)]))
	bot.add_rule(rsBotRule('info', True, 'try !rules or !commands', [re.compile('^!help$', re.IGNORECASE)]))

	# echo
	bot.add_rule(rsBotRule('echo', True, '$$match_1', [re.compile('^!echo\s(.*)$', re.IGNORECASE)]))

	bot.run()

# lobby {
# 	"mType": 15,
# 	"mTime": 1585990254,
# 	"mTime_sixtyfour_str": "1585990254",
# 	"mChatMessage": {
# 		"chat_id": {
# 			"broadcast_status_peer_id": "00000000000000000000000000000000",
# 			"type": 3,
# 			"peer_id": "00000000000000000000000000000000",
# 			"distant_chat_id": "00000000000000000000000000000000",
# 			"lobby_id": 17803486546125065896,
# 			"lobby_id_sixtyfour_str": "17803486546125065896"
# 		},
# 		"broadcast_peer_id": "00000000000000000000000000000000",
# 		"lobby_peer_gxs_id": "1b95d9a2f6762dae2c1f2fd338d47c4f",
# 		"peer_alternate_nickname": "",
# 		"chatflags": 0,
# 		"sendTime": 1585990254,
# 		"recvTime": 1585990254,
# 		"msg": "<body><style type=\"text/css\" RSOptimized=\"v2\">.S1{font-weight:400;}.S1{font-family:\\'NotoSansCJKJP\\';}.S0{color:#000000;}.S1{font-size:11pt;}.S1{font-style:normal;}</style><span><span class=\"S1\"><span class=\"S0\">a</span></span></span></body>",
# 		"incoming": True,
# 		"online": True
# 	}
# }

# broadcast {
# 	"chat_id": {
# 		"broadcast_status_peer_id": "00000000000000000000000000000000",
# 		"type": 4,
# 		"peer_id": "00000000000000000000000000000000",
# 		"distant_chat_id": "00000000000000000000000000000000",
# 		"lobby_id": 0,
# 		"lobby_id_sixtyfour_str": "0"
# 	},
# 	"broadcast_peer_id": "d6fb6c0f53d18303dcc9043111490e40",
# 	"lobby_peer_gxs_id": "00000000000000000000000000000000",
# 	"peer_alternate_nickname": "",
# 	"chatflags": 1,
# 	"sendTime": 1585991468,
# 	"recvTime": 1585991468,
# 	"msg": "<body><style type=\"text/css\" RSOptimized=\"v2\">.S1{font-weight:400;}.S1{font-family:\\'NotoSansCJKJP\\';}.S0{color:#000000;}.S1{font-size:11pt;}.S1{font-style:normal;}</style><span><span class=\"S1\"><span class=\"S0\">test</span></span></span></body>",
# 	"incoming": True,
# 	"online": True
# }

# private distant
# {
#     "chat_id": {
#         "broadcast_status_peer_id": "00000000000000000000000000000000",
#         "type": 2,
#         "peer_id": "00000000000000000000000000000000",
#         "distant_chat_id": "937feab871031cf4ba05d61190a7f940",
#         "lobby_id": 0,
#         "lobby_id_sixtyfour_str": "0"
#     },
#     "broadcast_peer_id": "00000000000000000000000000000000",
#     "lobby_peer_gxs_id": "00000000000000000000000000000000",
#     "peer_alternate_nickname": "",
#     "chatflags": 2,
#     "sendTime": 1586000100,
#     "recvTime": 1586000101,
#     "msg": "<body><style type=\"text/css\" RSOptimized=\"v2\">.S1{font-weight:400;}.S1{font-family:\\'NotoSansCJKJP\\';}.S0{color:#000000;}.S1{font-size:11pt;}.S1{font-style:normal;}</style><span><span class=\"S1\"><span class=\"S0\">distant</span></span></span></body>",
#     "incoming": True,
#     "online": True
# }

# private
# {
# 	"chat_id": {
# 		"broadcast_status_peer_id": "00000000000000000000000000000000",
# 		"type": 1,
# 		"peer_id": "fa8b0b2f12acb6285f9afb77b31767bd",
# 		"distant_chat_id": "00000000000000000000000000000000",
# 		"lobby_id": 0,
# 		"lobby_id_sixtyfour_str": "0"
# 	},
# 	"broadcast_peer_id": "00000000000000000000000000000000",
# 	"lobby_peer_gxs_id": "00000000000000000000000000000000",
# 	"peer_alternate_nickname": "",
# 	"chatflags": 2,
# 	"sendTime": 1586000106,
# 	"recvTime": 1586000107,
# 	"msg": "<body><style RSOptimized=\"v2\" type=\"text/css\">.S1{font-family:\\'Cantarell\\';}.S1{font-size:11pt;}.S1{font-weight:400;}.S0{color:#000000;}.S1{font-style:normal;}</style><span><span class=\"S1\"><span class=\"S0\">private</span></span></span></body>",
# 	"incoming": True,
# 	"online": True
# }
