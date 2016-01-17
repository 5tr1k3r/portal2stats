import requests
from bs4 import BeautifulSoup
from collections import namedtuple
import pickle
import markdown2
import webbrowser

WR = namedtuple('WR', ['holder', 'time'])
steam_ids = {'5tr1k3r': '76561198033958873',
             'Lee': '76561198028048389',
            'Робер Эпине': '76561197987834356'}
PR = namedtuple('PR', ['map', 'time', 'rank'])


class PortalMap:
    def __init__(self, packed_data):
        i, steam_id, lp_id, name, chapter_id, is_coop, is_public = packed_data
        self.steam_id = steam_id
        self.lp_id = lp_id
        self.name = name
        self.chapter_id = chapter_id
        self.is_coop = bool(is_coop)
        self.is_public = bool(is_public)


def get_map_list():
    from portal_data import raw_maps
    map_list = {}
    for level in raw_maps:
        map_list[level[0]] = PortalMap(level)
    return map_list


def convert_raw_time_to_centiseconds(time):
    minutes = 0
    if ':' in time:
        minutes, time = time.split(':')
    seconds, centiseconds = time.split('.')
    return int(minutes)*6000 + int(seconds)*100 + int(centiseconds)


def prettify_time(time):
    if time < 0:
        time = -time
        sign = '-'
    else:
        sign = ''
    x, centiseconds = divmod(time, 100)
    minutes, seconds = divmod(x, 60)
    if minutes:
        return '{}{:02}:{:02}.{:02}'.format(sign, minutes, seconds, centiseconds)
    return '{}{:02}.{:02}'.format(sign, seconds, centiseconds)


def get_world_records(map_list):
    try:
        with open('portal_wrs.pkl', 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        print('Retrieving WR data...')

    res = requests.get('http://board.ncla.me/home')
    res.raise_for_status()
    soup = BeautifulSoup(res.content, 'lxml')
    
    wrs = {}
    for level_id, level in map_list.items():
        if not level.is_coop:
            stuf = soup.find(style="background: url('/images/chambers/{}.jpg')".format(level.steam_id))
            stuf3 = stuf.parent.div.next_sibling.next_sibling.find(class_='firstplace')
            name = stuf3.find(class_='name').string
            raw_time = stuf3.find(class_='score').string
            time = convert_raw_time_to_centiseconds(raw_time)
            wrs[level_id] = WR(name, time)
    with open('portal_wrs.pkl', 'xb') as f:
        pickle.dump(wrs, f)
    return wrs


def get_top200(map_list):
    try:
        with open('portal_top200_times.pkl', 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        print('Retrieving top200 for each level...')

    top200 = {}
    for level_id, level in map_list.items():
        if not level.is_coop and level.is_public:
            res = requests.get('http://steamcommunity.com/stats/Portal2/leaderboards/{}?sr=200'.format(level.steam_id))
            res.raise_for_status()
            soup = BeautifulSoup(res.content, 'lxml')
            print(level_id, level.name)
            time = soup.find_all(class_='score')[-1].string.strip()
            top200[level_id] = convert_raw_time_to_centiseconds(time)

    with open('portal_top200_times.pkl', 'xb') as f:
        pickle.dump(top200, f)
    return top200


def get_players_results(steam_ids, map_list):
    try:
        with open('portal_players_results.pkl', 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        print('Retrieving players\' results...')

    players_results = {}
    for player in steam_ids:
        players_results[player] = {}
        for level_id, level in map_list.items():
            if not level.is_coop and level.is_public:
                time, rank = get_one_player_result(steam_ids[player], level.steam_id)
                print(player, level_id, level.name, time, rank)
                players_results[player][level_id] = PR(level.name, time, rank)

    with open('portal_players_results.pkl', 'xb') as f:
        pickle.dump(players_results, f)
    return players_results


def get_one_player_result(steam_id, level):
    res = requests.get('http://steamcommunity.com/profiles/{}/stats/Portal2/?tab=leaderboards&lb={}'.format(steam_id, level))
    res.raise_for_status()
    soup = BeautifulSoup(res.content, 'lxml')
    try:
        time = soup.find(class_='scoreh').string.strip()
    except AttributeError:
        return None, None
    try:
        rank = soup.find(class_='globalRankh').string.strip()
    except AttributeError:
        rank = soup.find(class_='globalRankh').a.string.strip()
    return convert_raw_time_to_centiseconds(time), int(rank.split('#')[1])


def evaluate_outcome(low, high, outcome, need_percent=False):
    percent_sign = '%' * need_percent
    if outcome >= high:
        return '<div class="bad" style="display: inline">{}{}</div>'.format(outcome, percent_sign)
    elif outcome <= low:
        return '<div class="good" style="display: inline">{}{}</div>'.format(outcome, percent_sign)
    return '{}{}'.format(outcome, percent_sign)


def print_player_times(players_results, player):
    html_doc = ['### {}\'s results'.format(player)]
    html_doc.append('Chapter | Map | Time | Rank | WR | % of WR | Abs. diff. | Top200 | % of top200 | Abs. diff.')
    html_doc.append('- | - | - | - | - | - | - | - | - | -')
    for level_id, result in players_results[player].items():
        if result.time:
            rank_evaluated = evaluate_outcome(200, 1000, result.rank)
            rel_wr_eval = evaluate_outcome(140, 250, round(result.time / wrs[level_id].time * 100, 1), need_percent=True)
            abs_wr_eval = prettify_time(result.time - wrs[level_id].time)
            rel_top200_eval = evaluate_outcome(110, 150, round(result.time / top200[level_id] * 100, 1), need_percent=True)
            abs_top200_eval = prettify_time(result.time - top200[level_id])
            html_doc.append('{} | {} | {} | {} | {} | {} | {} | {} | {} | {}'.format(maps[level_id].chapter_id-6, result.map, prettify_time(result.time), rank_evaluated, 
                                                                                     prettify_time(wrs[level_id].time), rel_wr_eval, abs_wr_eval,
                                                                                     prettify_time(top200[level_id]), rel_top200_eval, abs_top200_eval))
    html = markdown2.markdown('\n'.join(html_doc), extras=['tables'])
    with open('portal.html', 'w') as f:
        f.write('<head>\n<style>\n')
        with open('mystyle.css') as f2:
            f.write(f2.read())
        f.write('\n</head>\n</style>\n')
        f.write(html)
    webbrowser.open('portal.html')


def print_wrs(wrs, maps, is_public=True):
    total_wr_time = 0
    print('        Map               Player             Time')
    for wr in wrs:
        if maps[wr].is_public == is_public or not is_public:
            total_wr_time += wrs[wr].time
            print(maps[wr].chapter_id-6, '{:21}{:17}{:>10}'.format(maps[wr].name, wrs[wr].holder, prettify_time(wrs[wr].time)))
    print('-' * 50, '\nTotal Time:', prettify_time(total_wr_time))


def compare_two_players(a, b):
    html_doc = ['### {} vs {}'.format(a, b)]
    html_doc.append('Chapter | Map | A time | B time | Rel. diff. | Abs. diff.')
    html_doc.append('- | - | - | - | - | - ')
    a_tt = 0
    b_tt = 0
    for level in maps:
        if level in players_results[a] and players_results[a][level].time and players_results[b][level].time:
            a_tt += players_results[a][level].time
            b_tt += players_results[b][level].time
            temp_huec = round(players_results[a][level].time / players_results[b][level].time * 100, 1)
            if temp_huec <= 85 or temp_huec >= 118:
                rel_evaluated = '<div class="big_diff" style="display: inline">{}%</div>'.format(temp_huec)
            else:
                rel_evaluated = '{}%'.format(temp_huec)
            abs_diff = prettify_time(players_results[a][level].time - players_results[b][level].time)
            html_doc.append('{} | {} | {} | {} | {} | {}'.format(maps[level].chapter_id-6, maps[level].name, prettify_time(players_results[a][level].time), 
                                                                 prettify_time(players_results[b][level].time), rel_evaluated, abs_diff))

    html_doc.append('A total time: {}<br>B total time: {}<br>Difference: {}'.format(prettify_time(a_tt), prettify_time(b_tt), prettify_time(abs(a_tt - b_tt))))

    html = markdown2.markdown('\n'.join(html_doc), extras=['tables'])
    with open('player_comparison.html', 'w') as f:
        f.write('<head>\n<style>\n')
        with open('mystyle.css') as f2:
            f.write(f2.read())
        f.write('\n</head>\n</style>\n')
        f.write(html)
    webbrowser.open('player_comparison.html')



maps = get_map_list()
wrs = get_world_records(maps)
players_results = get_players_results(steam_ids, maps)
top200 = get_top200(maps)

# print_player_times(players_results, '5tr1k3r')

compare_two_players('5tr1k3r', 'Робер Эпине')

# print(get_one_player_result(steam_ids['5tr1k3r'], 47106))
# print_wrs(wrs, maps)
