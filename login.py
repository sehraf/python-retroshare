#!/usr/bin/env python3

import json, requests, argparse, getpass, sys

debug = False

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

		pass

	def sendRequest(self, function, data=None):
		if function[0] != '/':
			function = '/' + function
		url = 'http://' + self._ip + ':' + self._port + function

		debugDump('POST: ' + url, data)
		resp = requests.post(url=url, json=data, auth=self._auth)

		# gracefully add 401 error
		if resp.status_code == 401:
			return {'retval': False}

		debugDump('RESP', resp.json())
		return resp.json()


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='reads (ssl) id and (account) password')
	parser.add_argument('--identity', '-i', help='account id to login')
	parser.add_argument('--pass', '-P', help='(optional) password of the account', dest='password')
	parser.add_argument('--exit', '--shutdown', help='shutdown the instance instead of loging in', dest='shutdown', action="store_true")
	args, _ = parser.parse_known_args()

	rs = rsHost()

	if args.shutdown is not None and args.shutdown:
		rs.sendRequest('/rsControl/rsGlobalShutDown')
		sys.exit(0)

	if args.identity is None:
		print('ssl id missing!')
		sys.exit(1)
	ssl_id = args.identity

	if len(ssl_id) != 32:
		print('ssl id has the wrong length!')
		sys.exit(1)

	if args.password is None:
		# read pw from stdin
		password = getpass.getpass()
	else:
		password = args.password

	print('sending request (this can take a few seconds) ...')
	req = {'account': ssl_id, 'password': password}
	resp = rs.sendRequest('/rsLoginHelper/attemptLogin', data=req)
	print('success' if resp['retval'] == 0 else 'failure')
