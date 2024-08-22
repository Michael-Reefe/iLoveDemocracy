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
    output[0] = msg
    j = 1

    won = np.zeros(len(candidates), dtype=bool)

    if n_winners > 1:

        # Loop until we've chosen enough winners

        while np.sum(won) < n_winners:

            output = np.append(output, np.array(['']))

            # count up all the stars 
            stars = np.sum(ballots, axis=1)
            n_stars = np.sum(ballots)

            # pick the highest count as the winner
            won_stars = stars[won] 
            stars[won] = -999
            win = np.argmax(stars)
            stars[won] = won_stars
            won[win] = True

            msg = f'### STAR TALLIES FOR ROUND {j} ###'
            output[j] = msg + '\n'
            output[j] += print_star_tallies(candidates_padded, stars, n_stars, won)
            msg = f'####################################'
            output[j] += msg + '\n'

            msg = f'RESULTS: {candidates_padded[win]} HAS WON THE ELECTION' 
            output[j] += msg + '\n'

            if np.sum(won) < n_winners:
                # remove 1/n voters that voted for the winner for the next round
                win_voters = []
                for k in range(ballots.shape[1]): 
                    if ballots[win,k] == np.max(ballots[:,k]):
                        win_voters.append(k)
                n_win_voters = len(win_voters)
                n_to_remove = int(n_win_voters/n_winners)

                msg = f'{n_to_remove} OF THEIR VOTES WILL BE CONSIDERED "COUNTED" AND REMOVED FOR THE NEXT ROUND'
                output[j] += msg + '\n'

                ballots[:,win_voters[:n_to_remove]] = 0
            
            j += 1
        

        output = np.append(output, np.array(['']))
        
        # do a final print-out
        msg = f'### FINAL RESULTS            ###'
        output[j] += msg + '\n'
        output[j] += print_final_results(candidates_padded, None, 0, won)
        msg = f'################################'
        output[j] += msg + '\n'
        msg = f'I LOVE DEMOCRACY'
        output[j] += msg
    
    else:

        # count up all the stars 
        stars = np.sum(ballots, axis=1)
        n_stars = np.sum(ballots)

        # Pick the TWO highest candidates 
        ss = np.argsort(stars)
        won[ss[-2:]] = True
    
        output = np.append(output, np.array(['']))

        msg = f'### STAR TALLIES FOR ROUND 1 ###'
        output[1] = msg + '\n'
        output[1] += print_star_tallies(candidates_padded, stars, n_stars, won)
        msg = f'####################################'
        output[1] += msg + '\n'

        msg = f'RESULTS: {candidates_padded[won][0]} AND {candidates_padded[won][1]} HAVE PASSED ROUND ONE'  
        output[1] += msg + '\n'
        msg = f'THEY WILL NOW FACE OFF IN A HEAD-TO-HEAD MATCH'  
        output[1] += msg + '\n'

        # only consider ballots from the 2 highest performers
        ballots2 = ballots[won,:]
        candidates2 = candidates_padded[won]
        # give each candidate ONE vote based on whoever was ranked higher
        for j in range(ballots2.shape[1]):
            if ballots2[0,j] > ballots2[1,j]:
                ballots2[0,j] = 1
                ballots2[1,j] = 0
            elif ballots2[0,j] < ballots2[1,j]:
                ballots2[0,j] = 0
                ballots2[1,j] = 1
            else:
                ballots2[0,j] = 0
                ballots2[1,j] = 0
        
        # count the final round
        won = np.zeros(len(candidates2), dtype=bool)
        votes = np.sum(ballots2, axis=1)
        n_votes = np.sum(ballots2)
        win = np.argmax(votes)
        won[win] = True

        output = np.append(output, np.array(['']))

        # do a final print-out
        msg = f'### FINAL RESULTS            ###'
        output[2] += msg + '\n'
        output[2] += print_final_results(candidates2, votes, n_votes, won)
        msg = f'################################'
        output[2] += msg + '\n'
        msg = f'I LOVE DEMOCRACY'
        output[2] += msg
    
    return output

def print_star_tallies(candidates_padded, stars, n_stars, won):
    output = ''
    for c in range(len(candidates_padded)):
        status = 'WON       ' if won[c] else 'RUNNING   '
        msg = f'{status} | {candidates_padded[c]} | {str(int(stars[c])).zfill(4)} STARS ({stars[c]/n_stars*100:.1f}%)'
        output += msg + '\n'
    return output


def print_final_results(candidates_padded, votes, n_votes, won):
    output = ''
    for c in range(len(candidates_padded)):
        status = 'WON       ' if won[c] else 'LOST      '
        if votes is not None:
            msg = f'{status} | {candidates_padded[c]} | {str(int(votes[c])).zfill(4)} VOTES ({votes[c]/n_votes*100:.1f}%)'
        else:
            msg = f'{status} | {candidates_padded[c]}'
        output += msg + '\n'
    return output

def simulate_election(n_winners=1):

    candidates = ['Joe', 'Mary', 'Humpty Dumpty', 'SpongeBob SquarePants', 'NGC 4609']

    n_voters = 1000
    ballots = np.random.randint(low=0, high=5, size=(len(candidates), n_voters))

    output = run_election(candidates, ballots, n_winners)

    print(''.join(output))
