# This file handles the ranked choice vote logic
import numpy as np

def run_election(candidates: np.ndarray, ballots: np.ndarray):
    # candidates should be a 1D array labeling each candidate in the vote
    # ballots should be a 2D array: first index iterates over candidates, second index iterates over voters
    #    for example, if there are 5 candidates index [:,2] should look like [5,3,1,2,4] giving the rankings of each candidate
    #    anything 0 or lower means no vote, i.e. [0,0,1,2,0] would indicate that no vote should be counted for the 1st, 2nd, or 5th candidate
    output = ''

    candidates_padded = np.copy(candidates)
    maxcharlen = np.max([len(cand) for cand in candidates])
    for c in range(len(candidates_padded)):
        diff = maxcharlen - len(candidates_padded[c])
        if diff > 0:
            candidates_padded[c] += ' '*diff

    output += 'BEGINNING ELECTION\n'
    j = 0
    eliminated = np.zeros(len(candidates), dtype=bool)

    while True:
        
        # tally up the 1st choice votes
        n_votes = ballots.shape[1]
        fracs = np.sum(ballots == 1, axis=1) / n_votes
        n_cands = np.sum(fracs > 0)

        output += f'### VOTE TALLIES FOR ROUND {j+1} ###\n'
        for c in range(len(candidates)):
            status = 'RUNNING   ' if fracs[c] > 0 else 'ELIMINATED'
            output += f'{status} | {candidates_padded[c]} | {fracs[c]*100:.1f}%\n'
        output += f'####################################\n'

        # first, check if any candidate has more than 50% of the vote as their 1st choice
        if np.any(fracs > 0.5):
            wh = np.where(fracs > 0.5)[0][0]
            output += f'RESULTS: {candidates_padded[wh]} HAS WON THE ELECTION WITH A MAJORITY OF {fracs[wh]*100:.1f}%\n'
            output += f'I LOVE DEMOCRACY'
            return candidates[wh], output

        # second, check if there is only one candidate remaining
        if n_cands == 1:
            wh = np.where(fracs > 0)[0][0]
            output += f'RESULTS: {candidates_padded[wh]} HAS WON THE ELECTION WITH {fracs[wh]*100:.1f}% OF VOTES\n'
            output += f'DUE TO THE ELIMINATION OF ALL OTHER CANDIDATES\n'
            output += f'I LOVE DEMOCRACY'
            return candidates[wh], output

        # nobody got more than 50% of the vote, but there are more candidates remaining
        # eliminate the worst candidate and redistribute their votes to their next choice
        minfrac = np.min(fracs[~eliminated])
        last = np.where(fracs == minfrac)[0][0]
        eliminated[last] = True

        wh = np.where(ballots[last,:] == 1)[0]
        # iterate through each voters' next choice until it's someone who hasn't already been eliminated
        for whi in wh:
            ballots[:,whi] -= 1
            nextcand = np.where(ballots[:,whi] == 1)[0]
            while len(nextcand) > 0 and eliminated[nextcand]:
                ballots[:,whi] -= 1
                nextcand = np.where(ballots[:,whi] == 1)[0]

        output += f'RESULTS: {candidates_padded[last]} HAS BEEN ELIMINATED FROM THE RACE WITH {fracs[last]*100:.1f}% OF VOTES\n'
        output += f'THE ELECTION WILL CONTINUE\n'

        j += 1


def simulate_election():

    candidates = ['Joe', 'Mary', 'Humpty Dumpty', 'SpongeBob SquarePants', 'NGC 4609']

    n_voters = 1000
    ballots = np.zeros((len(candidates), n_voters), dtype=int)
    for i in range(n_voters):
        ballots[:,i] = np.arange(1,len(candidates)+1)
        np.random.shuffle(ballots[:,i])
    
    run_election(candidates, ballots)
