import requests
from bs4 import BeautifulSoup
from collections import namedtuple
from maps import raw_maps
import pickle
import markdown2
import webbrowser


WR = namedtuple('WR', ['holder', 'time'])
PR = namedtuple('PR', ['map', 'time', 'rank'])
PR2 = namedtuple('PR2', ['map', 'time', 'rank', 'new'])
PortalMap = namedtuple('PortalMap', ['i', 'steam_id', 'lp_id', 'name', 'chapter_id', 'is_coop', 'is_public'])
steam_ids = {'5tr1k3r': '76561198033958873',
             'Lee': '76561198028048389',
             'Робер Эпине': '76561197987834356',
             'Burton': '76561198015709276'}


def get_map_list():
    map_list = {}
    for level in raw_maps:
        map_list[level[0]] = PortalMap(*level)
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
        return '{}{}:{:02}.{:02}'.format(sign, minutes, seconds, centiseconds)
    return '{}{}.{:02}'.format(sign, seconds, centiseconds)


def handle_pickle_loading(filename, loading_message):
    try:
        with open(filename, 'rb') as f:
            return pickle.load(f)
    except (FileNotFoundError, EOFError):
        print(loading_message)


def get_site_contents(link):
    res = requests.get(link)
    res.raise_for_status()
    return BeautifulSoup(res.content, 'lxml')


def dump_pickle_n_return_data(filename, data):
    with open(filename, 'wb') as f:
        pickle.dump(data, f)
    return data


def get_world_records(map_list):
    pickle_file = 'pickles\\portal_wrs.pkl'
    wrs_pickled = handle_pickle_loading(pickle_file, 'Retrieving WR data...')
    if wrs_pickled:
        return wrs_pickled

    soup = get_site_contents('http://board.ncla.me/home')
    chamber_selector = soup.select('.titlebg a')
    wr_selector = soup.select('.firstplace .score')
    name_selector = soup.select('.firstplace .name')
    temp_level_ids = {v.steam_id: k for k, v in map_list.items()}
    wrs = {temp_level_ids[int(k['href'].split('/')[2])]: WR(str(v2.string), convert_raw_time_to_centiseconds(v.string)) \
        for k, v, v2 in zip(chamber_selector, wr_selector, name_selector)}
    return dump_pickle_n_return_data(pickle_file, wrs)


def get_top200(map_list):
    pickle_file = 'pickles\\portal_top200_times.pkl'
    top200_pickled = handle_pickle_loading(pickle_file, 'Retrieving top200 for each level...')
    if top200_pickled:
        return top200_pickled

    top200 = {}
    for level_id, level in map_list.items():
        if not level.is_coop and level.is_public:
            soup = get_site_contents('http://steamcommunity.com/stats/Portal2/leaderboards/{}?sr=200'.format(level.steam_id))
            print(level_id, level.name)
            raw_time = soup.find_all(class_='score')[-1].string.strip()
            top200[level_id] = convert_raw_time_to_centiseconds(raw_time)
    return dump_pickle_n_return_data(pickle_file, top200)


def get_players_results(steam_ids, map_list, update=False):
    """ Try and load players' results from pickles and compare them with freshly web-scraped ones if asked so. """
    pickle_file = 'pickles\\portal_players_results.pkl'
    pr_pickled = handle_pickle_loading(pickle_file, 'Retrieving players\' results...')
    if pr_pickled and not update:
        return pr_pickled

    if not pr_pickled:
        pr_pickled = {}
    temp_players_results = {}
    for player in update:
        temp_players_results[player] = {}
        for level_id, level in map_list.items():
            if not level.is_coop and level.is_public:
                time, rank = get_one_player_result(steam_ids[player], level.steam_id)
                is_new = not(time == pr_pickled[player][level_id].time)
                print(is_new * 'NEW RESULT', player, level_id, level.name, time, rank)
                temp_players_results[player][level_id] = PR2(level.name, time, rank, is_new)

    pr_pickled.update(temp_players_results)
    return dump_pickle_n_return_data(pickle_file, pr_pickled)


def get_one_player_result(steam_id, level):
    soup = get_site_contents('http://steamcommunity.com/profiles/{}/stats/Portal2/?tab=leaderboards&lb={}'.format(steam_id, level))
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
        return '<div class="bad">{}{}</div>'.format(outcome, percent_sign)
    elif outcome <= low:
        return '<div class="good">{}{}</div>'.format(outcome, percent_sign)
    return '{}{}'.format(outcome, percent_sign)


def make_table_head(caption, data):
    html_doc = []
    html_doc.append(caption)
    html_doc.append(' | '.join(data))
    html_doc.append('-' + ' | -' * (len(data)-1))
    return html_doc


def fill_table(html_doc, data):
    html_doc.append(' | '.join(map(str, data)))
    return html_doc


def markdown_stuff_and_open_browser(html_doc, link, css_link):
    head = """<!DOCTYPE html>
<head>
<title>Portal 2 challenge times</title>
<link rel="stylesheet" type="text/css" href={}>
</head>
""".format(css_link)
    with open(link, 'w') as f:
        f.write(head)
        f.write(markdown2.markdown('\n'.join(html_doc), extras=['tables']))
    webbrowser.open(link)


def print_player_times(players_results, player):
    try:
        assert player in players_results
    except AssertionError:
        print('No such player in the database!')
        return

    player_tt = 0
    wr_tt = 0
    top200_tt = 0
    lev_count = 0
    html_doc = make_table_head('### {}\'s results'.format(player), ('Chapter', 'Map', 'Time', 'Rank', 'New', 'WR', '% of WR', 'Abs. diff.', 'Top200', '% of top200', 'Abs. diff.'))
    for level_id, result in players_results[player].items():
        if result.time:
            player_tt += result.time
            wr_tt += wrs[level_id].time
            top200_tt += top200[level_id]
            lev_count += 1
            rank_evaluated = evaluate_outcome(200, 1000, result.rank)
            rel_wr_eval = evaluate_outcome(140, 250, round(result.time / wrs[level_id].time * 100, 1), need_percent=True)
            abs_wr_eval = prettify_time(result.time - wrs[level_id].time)
            rel_top200_eval = evaluate_outcome(110, 150, round(result.time / top200[level_id] * 100, 1), need_percent=True)
            abs_top200_eval = prettify_time(result.time - top200[level_id])
            is_new = result.new * 'Yes'
            data = (maps[level_id].chapter_id-6, result.map, prettify_time(result.time), rank_evaluated, is_new,
                    prettify_time(wrs[level_id].time), rel_wr_eval, abs_wr_eval, 
                    prettify_time(top200[level_id]), rel_top200_eval, abs_top200_eval)
            html_doc = fill_table(html_doc, data)
    html_doc.append('Levels completed: {}/{}<br>'.format(lev_count, len(top200)))
    html_doc.append('{}\'s Total Time: {}<br>'.format(player, prettify_time(player_tt)))
    html_doc.append('Top200 Total Time: {}<br>'.format(prettify_time(top200_tt)))
    html_doc.append('WR Total Time: {}'.format(prettify_time(wr_tt)))
    markdown_stuff_and_open_browser(html_doc, r'..\pages\portal.html', "mystyle.css")


def print_wrs(wrs, maps, is_public=True):
    total_wr_time = 0
    html_doc = make_table_head('### World Records', ('Chapter', 'Map', 'Player', 'Time'))
    for wr in wrs:
        if maps[wr].is_public == is_public or not is_public:
            total_wr_time += wrs[wr].time
            html_doc = fill_table(html_doc, (maps[wr].chapter_id-6, maps[wr].name, wrs[wr].holder, prettify_time(wrs[wr].time)))
    html_doc.append('Total Time: {}'.format(prettify_time(total_wr_time)))
    markdown_stuff_and_open_browser(html_doc, r'..\pages\world_records.html', "wr_style.css")


def compare_two_players(a, b, players_results, maps):
    try:
        assert a in players_results and b in players_results
    except AssertionError:
        print('No such player in the database!')
        return

    html_doc = make_table_head('### {} vs {}'.format(a, b), ('Chapter', 'Map', 'A time', 'B time', 'Rel. diff.', 'Abs. diff.'))
    a_tt = 0
    b_tt = 0
    for level in maps:
        if level in players_results[a] and players_results[a][level].time and players_results[b][level].time:
            a_tt += players_results[a][level].time
            b_tt += players_results[b][level].time
            temp_huec = round(players_results[a][level].time / players_results[b][level].time * 100, 1)
            if temp_huec <= 85 or temp_huec >= 118:
                rel_evaluated = '<div class="big_diff">{}%</div>'.format(temp_huec)
            else:
                rel_evaluated = '{}%'.format(temp_huec)
            abs_diff = prettify_time(players_results[a][level].time - players_results[b][level].time)
            data = (maps[level].chapter_id-6, maps[level].name, prettify_time(players_results[a][level].time), 
                    prettify_time(players_results[b][level].time), rel_evaluated, abs_diff)
            html_doc = fill_table(html_doc, data)

    html_doc.append('A total time: {}<br>B total time: {}<br>Difference: {}'.format(prettify_time(a_tt), prettify_time(b_tt), prettify_time(abs(a_tt - b_tt))))
    markdown_stuff_and_open_browser(html_doc, r'..\pages\player_comparison.html', "comparison_style.css")


maps = get_map_list()
wrs = get_world_records(maps)
players_to_update = ['5tr1k3r']
players_results = get_players_results(steam_ids, maps)
top200 = get_top200(maps)

print_player_times(players_results, 'Робер Эпине')

# compare_two_players('5tr1k3r', 'Робер Эпине', players_results, maps)

# print_wrs(wrs, maps)
