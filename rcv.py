# This file handles the ranked choice vote logic
import numpy as np

def run_election(candidates: np.ndarray, ballots: np.ndarray, n_winners: int = 1):
    # candidates should be a 1D array labeling each candidate in the vote
    # ballots should be a 2D array: first index iterates over candidates, second index iterates over voters
    #    for example, if there are 5 candidates index [:,2] should look like [5,3,1,2,4] giving the rankings of each candidate
    #    anything 0 or lower means no vote, i.e. [0,0,1,2,0] would indicate that no vote should be counted for the 1st, 2nd, or 5th candidate
    # n_winners is an integer specifying how many winners the poll should have, it defaults to 1
    # if n_winners is > 1, the voting uses the Single Transferable Vote (STV)
    output = np.array([''], dtype=object)

    # pad candidate names with spaces so printing looks uniform
    candidates_padded = np.copy(candidates)
    maxcharlen = np.max([len(cand) for cand in candidates])
    for c in range(len(candidates_padded)):
        diff = maxcharlen - len(candidates_padded[c])
        if diff > 0:
            candidates_padded[c] += ' '*diff

    msg = 'BEGINNING ELECTION'
    print(msg)
    output[0] = msg
    j = 1
    eliminated = np.zeros(len(candidates), dtype=bool)
    won = np.zeros(len(candidates), dtype=bool)
    # use Droop's quota for votes
    n_votes = ballots.shape[1]
    n_to_win = int((n_votes / (n_winners + 1)) + 1)
    # increment until we have enough winners
    current_winners = 0

    while True:
        
        output = np.append(output, np.array(['']))
        
        # tally up the 1st choice votes
        votes = np.sum(ballots == 1, axis=1)
        n_cands = np.sum(votes > 0)

        msg = f'### VOTE TALLIES FOR ROUND {j} ###'
        print(msg)
        output[j] = msg + '\n'
        output[j] += print_vote_tallies(candidates_padded, votes, n_votes, won)
        msg = f'####################################'
        print(msg)
        output[j] += msg + '\n'

        # first, check if any candidate has more than the threshold of the vote as their 1st choice
        if np.any(votes[~won] >= n_to_win):

            # temporarily set the winners' votes to 0 so they arent counted in the search
            winner_votes = votes[won]
            votes[won] = -999
            votes[eliminated] = -999
            wh = np.where(votes >= n_to_win)[0][0]
            # set them back
            votes[won] = winner_votes
            votes[eliminated] = 0

            msg = f'RESULTS: {candidates_padded[wh]} HAS WON THE ELECTION WITH {str(int(votes[wh])).zfill(4)} VOTES ({votes[wh]/n_votes*100:.1f}%)'
            current_winners += 1 
            won[wh] = True
            print(msg)
            output[j] += msg + '\n'

            # if we've reached the target number of winners, stop the counting
            if current_winners >= n_winners:

                # do a final print-out
                msg = f'### FINAL VOTE TALLIES       ###'
                print(msg)
                output[j] += msg + '\n'
                output[j] += print_vote_tallies(candidates_padded, votes, n_votes, won, final=True)
                msg = f'################################'
                print(msg)
                output[j] += msg + '\n'

                msg = f'I LOVE DEMOCRACY'
                print(msg)
                output[j] += msg
                return output

            # if we have allowed for multiple winners, we want to take the overflowing votes for the candidate that just won and give them to
            # the voters' next choices
            if n_winners > 1:
                msg = f'THE OVERFLOWING VOTES WILL BE REDISTRIBUTED TO THE OTHER CANDIDATES'
                print(msg)
                output[j] += msg + '\n'

                # all ballots after this are shifted to their next choice
                whn = np.where(ballots[wh,:] == 1)[0][int(n_to_win):]
                ballots = shift_ballots(whn, ballots, eliminated, won)

                # restart the loop so that we recount all the votes before deciding to eliminate anyone
                msg = f'THE ELECTION WILL CONTINUE'
                print(msg)
                output[j] += msg + '\n'
                j += 1

                continue

        # second, check if the remaining number of candidates equals the remaining number of seats
        if n_cands <= (n_winners - current_winners):

            # if so, set all remaining candidates to winners
            winner_votes = votes[won]
            votes[won] = -999
            votes[eliminated] = -999
            wh = np.where(votes >= 0)[0]
            # set them back
            votes[won] = winner_votes
            votes[eliminated] = 0

            for whi in wh:
                msg = f'RESULTS: {candidates_padded[whi]} HAS WON THE ELECTION WITH {str(int(votes[whi])).zfill(4)} VOTES ({votes[whi]/n_votes*100:.1f}%)\n'
                msg += f'DUE TO THE ELIMINATION OF ALL OTHER CANDIDATES\n'
                current_winners += 1
                won[whi] = True
                print(msg)
                output[j] += msg

            # do a final print-out
            msg = f'### FINAL VOTE TALLIES       ###'
            print(msg)
            output[j] += msg + '\n'
            output[j] += print_vote_tallies(candidates_padded, votes, n_votes, won, final=True)
            msg = f'################################'
            print(msg)
            output[j] += msg + '\n'


            msg = f'I LOVE DEMOCRACY'
            print(msg)
            output[j] += msg

            return output

        # nobody got a majority of the vote, but there are more candidates remaining
        # eliminate the worst candidate and redistribute their votes to their next choice
        minvote = np.min(votes[~eliminated & ~won])

        winner_votes = votes[won]
        votes[eliminated] = -999   # temporarily edit these so that minvote doesnt accidentally choose an already eliminated location
        votes[won] = -999
        last = np.where(votes == minvote)[0]
        votes[eliminated] = 0
        votes[won] = winner_votes

        last = last[0]
        eliminated[last] = True

        wh = np.where(ballots[last,:] == 1)[0]
        # iterate through each voters' next choice until it's someone who hasn't already been eliminated
        ballots = shift_ballots(wh, ballots, eliminated, won)

        msg = f'RESULTS: {candidates_padded[last]} HAS BEEN ELIMINATED FROM THE RACE WITH {str(int(votes[last])).zfill(4)} VOTES ({votes[last]/n_votes*100:.1f}%)\n'
        msg += f'THEIR VOTES WILL BE REDISTRIBUTED TO THE OTHER CANDIDATES\n'
        msg += f'THE ELECTION WILL CONTINUE'
        print(msg)
        output[j] += msg + '\n'

        if j > 100:
            msg = f'CRITICAL: SOMETHING HAS GONE WRONG, THE VOTING HAS GONE ON FOR 1000 ROUNDS. STOPPING ELECTION.'
            print(msg)
            output[j] += msg
            return output

        j += 1


def shift_ballots(wh, ballots, eliminated, won):
    for whi in wh:
        ballots[:,whi] -= 1
        nextcand = np.where(ballots[:,whi] == 1)[0]
        while len(nextcand) > 0 and (eliminated[nextcand] or won[nextcand]):
            ballots[:,whi] -= 1
            nextcand = np.where(ballots[:,whi] == 1)[0]
    return ballots


def print_vote_tallies(candidates_padded, votes, n_votes, won, final=False):
    output = ''
    for c in range(len(candidates_padded)):
        status = 'WON       ' if won[c] else 'RUNNING   ' if (votes[c] > 0 and not final) else 'ELIMINATED'
        msg = f'{status} | {candidates_padded[c]} | {str(int(votes[c])).zfill(4)} | {votes[c]/n_votes*100:.1f}%'
        print(msg)
        output += msg + '\n'
    return output


def simulate_election(n_winners=1):

    candidates = ['Joe', 'Mary', 'Humpty Dumpty', 'SpongeBob SquarePants', 'NGC 4609']

    n_voters = 1000
    ballots = np.zeros((len(candidates), n_voters), dtype=int)
    for i in range(n_voters):
        ballots[:,i] = np.arange(1,len(candidates)+1)
        np.random.shuffle(ballots[:,i])
    
    run_election(candidates, ballots, n_winners)
