def init_parser(parser):
	parser.add_argument('--lr', type = float, default = 0.01, metavar = 'LR', help = 'learning rate')
	parser.add_argument('--frame-history-len', type = int, default = 3)
	parser.add_argument('--pred-step', type = int, default = 15)
	parser.add_argument('--batch-size', type = int, default = 32)
	parser.add_argument('--save-freq', type = int, default = 10)
	parser.add_argument('--save-path', type = str, default = 'mpc_12_step')
	parser.add_argument('--normalize', action = 'store_true')
	parser.add_argument('--buffer-size', type = int, default = 50000)
	parser.add_argument('--num-total-act', type = int, default = 2)
	parser.add_argument('--epsilon-frames', type = int, default = 50000)
	parser.add_argument('--learning-starts', type = int, default = 100)
	parser.add_argument('--learning-freq', type = int, default = 100)
	parser.add_argument('--target-update-freq', type = int, default = 100)
	parser.add_argument('--batch-step', type = int, default = 400)
	parser.add_argument('--resume', type = bool, default = False)

	# enviroument configurations
	parser.add_argument('--env', type = str, default = 'torcs-v0', metavar = 'ENV', help = 'environment')
	parser.add_argument('--xvfb', type = bool, default = True)
	parser.add_argument('--game-config', type = str, default = '/media/xinleipan/data/git/pyTORCS/game_config/michigan.xml')
	parser.add_argument('--continuous', action = 'store_true')

	# model configurations
	parser.add_argument('--pretrained', type = bool, default = True)
	parser.add_argument('--drn-model', type = str, default = 'drn_d_22')
	parser.add_argument('--classes', type = int, default = 4)

	parser.add_argument('--use-pos', action = 'store_true')
	parser.add_argument('--use-angle', action = 'store_true')
	parser.add_argument('--use-speed', action = 'store_true')
	parser.add_argument('--use-seg', action = 'store_true')
	parser.add_argument('--use-xyz', action = 'store_true')
	parser.add_argument('--use-dqn', action = 'store_true')

	parser.add_argument('--hidden-dim', type = int, default = 1024)
	parser.add_argument('--info-dim', type = int, default = 32)