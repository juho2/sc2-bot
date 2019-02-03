import argparse
import asyncio
import logging
import aiohttp
import random
import sys
import sc2
from sc2 import run_game, maps, Race, Difficulty, portconfig, Result
from sc2.player import Bot, Computer, Human
from sc2.client import Client
from sc2.protocol import ConnectionAlreadyClosed
from protoss import ProtossBot
import os
from multiprocessing import Pool, cpu_count
import time

# maps_list = ["AcidPlantLE", "BlueshiftLE", "CeruleanFallLE", "DreamcatcherLE",
#              "FractureLE", "LostAndFoundLE", "ParaSiteLE",
#              "Automaton LE", "Kairos Junction LE", "Port Aleksander LE", "Stasis LE"]

maps_dir = r'C:\Program Files (x86)\StarCraft II\Maps'
maps_list = [fname.split('.')[0] for _, _, files in os.walk(maps_dir) for fname in files if fname.endswith('.SC2Map')]
races = {"Terran": Race.Terran, "Zerg": Race.Zerg, "Protoss": Race.Protoss, "Random": Race.Random}

# python -m cProfile -s cumtime seebot.py > prof

# Modified code from https://github.com/Hannessa/sc2-bots
# Run ladder game
# This lets python-sc2 connect to a LadderManager game: https://github.com/Cryptyc/Sc2LadderServer
# Based on: https://github.com/Dentosal/python-sc2/blob/master/examples/run_external.py


def run_ladder_game(bot):
    # Load command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--GamePort', type=int, nargs="?", help='Game port')
    parser.add_argument('--StartPort', type=int, nargs="?", help='Start port')
    parser.add_argument('--LadderServer', type=str, nargs="?", help='Ladder server')
    parser.add_argument('--ComputerOpponent', type=str, nargs="?", help='Computer opponent')
    parser.add_argument('--ComputerRace', type=str, nargs="?", help='Computer race')
    parser.add_argument('--ComputerDifficulty', type=str, nargs="?", help='Computer difficulty')
    parser.add_argument('--OpponentId', type=str, nargs="?", help='Opponent ID')
    args, unknown = parser.parse_known_args()

    if args.LadderServer is None:
        host = "127.0.0.1"
    else:
        host = args.LadderServer

    host_port = args.GamePort
    lan_port = args.StartPort

    # Port config
    ports = [lan_port + p for p in range(1, 6)]

    pcfg = portconfig.Portconfig()
    pcfg.shared = ports[0]  # Not used
    pcfg.server = [ports[1], ports[2]]
    pcfg.players = [[ports[3], ports[4]]]

    # Join ladder game
    g = join_ladder_game(
        host=host,
        port=host_port,
        players=[bot],
        realtime=False,
        pcfg=pcfg
    )

    # Run it
    result = asyncio.get_event_loop().run_until_complete(g)
    print(result)


# Modified version of sc2.main._join_game to allow custom host and port, and to not spawn an additional sc2process
# (thanks to alkurbatov for fix)
async def join_ladder_game(host, port, players, realtime, pcfg, save_replay_as=None, step_time_limit=None,
                           game_time_limit=None):
    ws_url = "ws://{}:{}/sc2api".format(host, port)
    ws_connection = await aiohttp.ClientSession().ws_connect(ws_url, timeout=120)
    client = Client(ws_connection)

    try:
        result = await sc2.main._play_game(players[0], client, realtime, pcfg, step_time_limit, game_time_limit)
        if save_replay_as is not None:
            await client.save_replay(save_replay_as)
        await client.leave()
        await client.quit()
    except ConnectionAlreadyClosed:
        logging.error(f"Connection was closed before the game ended")
        return None
    finally:
        ws_connection.close()

    return result


def run_vs_human(bot):
    parser = argparse.ArgumentParser()
    parser.add_argument('--Race', type=str, nargs="?", help='Human player race: ' + ', '.join(races.keys()))
    parser.add_argument('--Map', type=str, nargs="?", help='one of: ' + ', '.join(maps_list))
    args, unknown = parser.parse_known_args()

    if args.Race not in races or args.Map not in maps_list:
        parser.print_usage()
        return

    run_game(maps.get(args.Map), [Human(races[args.Race]), bot], realtime=True, save_replay_as="Last.SC2Replay")


def main(num):
    bot = Bot(Race.Protoss, ProtossBot())
    enemy_race = random.choice([Race.Terran, Race.Zerg, Race.Protoss])
    enemy = Computer(enemy_race, Difficulty.CheatInsane)  # CheatInsane CheatMoney CheatVision VeryHard
    """
    sys.path.append('..\sc2-bots\cannon-lover')
    from cannon_lover_bot import CannonLoverBot
    enemy = Bot(Race.Protoss, CannonLoverBot())
    """
    if "--LadderServer" in sys.argv:
        # Ladder game started by LadderManager
        print("Starting ladder game...")
        run_ladder_game(bot)
    elif "--Race" in sys.argv:
        print("Starting game vs human...")
        run_vs_human(bot)
    else:
        print("Starting local game...", num)
        map_name = random.choice(maps_list)
        # map_name = "DarknessSanctuaryLE" # DarknessSanctuaryLE
        res = run_game(maps.get(map_name), [bot, enemy], realtime=False,)  # save_replay_as="Last.SC2Replay")
        end_time = str(time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime(time.time())))
        if res == Result.Victory:
            with open('wins.txt', 'a') as f:
                f.write(','.join([end_time, str(enemy_race), map_name]) + '\n')
            return(1)
        else:
            with open('losses.txt', 'a') as f:
                f.write(','.join([end_time, str(enemy_race), map_name]) + '\n')
            return(0)


if __name__ == '__main__':
    games_to_play = 16
    n_processes = cpu_count() #- 1

    with Pool(n_processes) as p:
        results = p.map(main, range(games_to_play))
    print('Won {}/{} games'.format(sum(results), len(results)))
