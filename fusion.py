import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
import re


def get_html(region):
    page = requests.get("https://liquipedia.net/rocketleague/Johnnyboi_i/Fusion/{}/Qualifier".format(region))
    soup = BeautifulSoup(page.content, 'html.parser')
    return soup

def get_roster(soup):
    # Extract rosters for teams
    teams = soup.find_all('div', class_='teamcard')
    
    # Get region
    region = soup.title.text.split(':')[0].split('- ')[1]
    
    d = defaultdict(list)
    rosters = []
    
    for team in teams:
        team_name = team.find('a').text
        team_link = team.find('a')['href']
    
        names = team.tbody.find_all('tr')
        
        # Iterate over players in a team
        for name in names:
            country = name.find('a')['title']
            player = name.find_all('a')[-1].text
            number = name.th.text
            
            row = [player, country, number, team_name, team_link, region]
            rosters.append(row)
            
            d[team_name].append((player, country, number))
    
    rosters = pd.DataFrame(rosters)
    rosters.columns = ['player', 'country', 'number', 'team', 'url', 'region']
    
    return rosters


def get_game_list(soup):
    # Extract match information from bracket
    bracket = soup.find('div', class_='bracket-wrapper bracket-team')
    matches = bracket.find_all('div', class_='bracket-game')
    
    # Get region
    region = soup.title.text.split(':')[0].split('- ')[1]
    
    # Iterate over matches to get game information
    game_list = []
    for match in matches:
        # There are some "matches" that aren't actually matches in the bracket
        if match.find('div', class_ = 'bracket-team-middle') is not None:
            continue
        
        # Game Type information (1v1, 2v2, 3v3)
        regex = re.compile('border')
        game_types = match.find('div', class_='bracket-popup-body-comment').find_all('div', attrs={'style':regex})
    
        # Extract scores
        games = match.find_all('div', class_='bracket-popup-body-match')
        team0_match_score, team1_match_score = [score.text for score in match.find_all('div', class_='bracket-score')]
    
        # General match info
        match_info = match.find('div', class_ = 'bracket-popup-body').find('span', class_='timer-object')
        time = match_info.text
    
        # Team names
        header = match.find('div', class_='bracket-popup-header')
        a = header.find_all('span')
        team0, team1 = a[2].a['title'], a[-2].a['title']
    
        # Iterate over game and game type
        for game, gt in zip(games, game_types):
            # Score
            team0_score = game.find('div', attrs={'style':'float:left;margin-left:5px;'}).text
            team1_score = game.find('div', attrs={'style':'float:right;margin-right:5px;'}).text
            
            # OT
            stadium = game.find('div', attrs={'style':''}).text
            ot = 'OT' in stadium
            if ot:
                ot_time = stadium.split('+')[-1][:-1]
            else:
                ot_time = '0:00'
    
            # Game Number and Game Type (player_num)
            number = gt.find('div', attrs={'style': 'font-weight:bold'}).text
            game_num = int(number.split()[1])
            pattern = '\dv\d'
            regex = re.search(pattern, number, re.IGNORECASE)
            player_num = int(regex.group(0)[0])
    
            # Store players in team list
            player_lists = gt.find_all('span', attrs={'style': 'white-space: pre'})
            player_list = [player.text for player in player_lists]       
            team0_pl, team1_pl = sorted(player_list[:player_num]), sorted(player_list[player_num:])
            if player_num == len(team0_pl) and player_num == len(team1_pl):
                pass
            else:
                print('player number and player lists do not match')
            
            game_info = [team0, team1, team0_score, team1_score, ot, ot_time, team0_pl, team1_pl, game_num, player_num, time, region, team0_match_score, team1_match_score]
            game_list.append(game_info)
    
    game_list = pd.DataFrame(game_list)
    game_list.columns = ['team0', 'team1', 'team0_score', 'team1_score', 'ot', 'ot_time', 'team0_pl', 'team1_pl', 'game_num', 'player_num', 'time', 'region', 'team0_match_score', 'team1_match_score']
    
    game_list = game_list.astype({col:float for col in ['team0_score', 'team1_score']})
    game_list['team0_win'] = game_list['team0_score'] > game_list['team1_score']
    game_list['team1_win'] = game_list['team1_score'] > game_list['team0_score']
    game_list['goals_scored'] = game_list['team0_score'] + game_list['team1_score']
    
    return game_list


na_soup = get_html('North_America')
eu_soup = get_html('Europe')


# Rosters
na_rosters = get_roster(na_soup)
eu_rosters = get_roster(eu_soup)
rosters = pd.concat([na_rosters, eu_rosters], ignore_index=True)
rosters.to_csv(r'./fusion_output/rosters.csv', index=False)


# Game List
na_game_list = get_game_list(na_soup)
eu_game_list = get_game_list(eu_soup)
game_list = pd.concat([na_game_list, eu_game_list], ignore_index=True)
game_list.to_csv(r'./fusion_output/game_list.csv', index=False)


# Construct Team df
# Construct dfs for home teams and away teams
t0 = game_list.groupby(['team0', 'player_num', 'region']).agg({'team0_win': ['sum', 'count'], 'team0_score': 'sum', 'team1_score': 'sum'}).reset_index()
t1 = game_list.groupby(['team1', 'player_num', 'region']).agg({'team1_win': ['sum', 'count'], 'team1_score': 'sum', 'team0_score': 'sum'}).reset_index()

cols = ['team', 'player_num', 'region', 'W', 'GP', 'goals for', 'goals against']
t0.columns = cols
t1.columns = cols

t0 = t0.set_index(cols[:3])
t1 = t1.set_index(cols[:3])

t0 = t0.astype({col:float for col in t0.columns})
t1 = t1.astype({col:float for col in t1.columns})

t = t0.add(t1, fill_value=0)

t = t.astype({col:int for col in ['W', 'goals for', 'goals against', 'GP']})
t['win_pct'] = round(((t.W/t.GP)*100)).astype(int)
t['L'] = (t.GP - t.W).astype(int)

t = t.sort_values(['player_num', 'win_pct', 'W', 'GP', 'team'], ascending=[False, False, False, True, True]).reset_index()
t.columns = ['Team', 'Game Type', 'Region', 'Wins', 'Games Played', 'GF', 'GA', 'Win Percentage', 'Losses']

t.to_csv(r'./fusion_output/teams.csv', index=False)
