select
    {{ int_('TeamID') }} as team_id,
    {{ param_('Season') }} as season,
    Conference as conference,
    Division as division,
    {{ int_('PlayoffRank') }} as conference_rank,
    {{ int_('LeagueRank') }} as league_rank,
    {{ int_('WINS') }} as wins,
    {{ int_('LOSSES') }} as losses,
    HOME as home_record,
    ROAD as road_record,
    {{ int_('LongWinStreak') }} as longest_win_streak,
    {{ int_('LongLossStreak') }} as longest_loss_streak,
    {{ num_('ConferenceGamesBack') }} as conference_games_back
from {{ source('landing', 'leaguestandingsv3__standings') }}
where TeamID is not null
{{ latest_file_per('_params') }}
