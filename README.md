A simple discord app that allows you to set up ranked-choice voting polls (AKA the alternative vote).
For polls with multiple winners, it uses the Single Transferable Vote (STV).

To set up a poll, use the command `/newpoll [name] [choice1] [choice2] ... [time limit] [description] [winners]`.
The arguments are the poll name, choices, time limit (in hours), description, and number of winners.

To get a ballot for a poll, use the button that shows up when the poll is created, or use the command
`/getballot [name]`.

To close a poll manually, use the the button that shows up when the poll is created, or use the command
`/closepoll [name]`.

For those unfamiliar, a ranked choice vote works like this:
	- Check if any candidate has more than 50% of the vote -> they win
	- Check if there is only one remaining candidate -> they win
	- Otherwise, eliminate the candidate with the least votes and redistribute those votes to
	  the 2nd ranked choice
	- Repeat until a winner is determined

The single transferable vote works in much the same way, except there can be multiple winners:
	- The threshold for winning is set by the number of slots available and the total number of votes;
	  this code uses the "Droop" critertion.
	- Any candidate that has votes in excess of the theshold will have the extra votes transferred
	  to other candidates based on what their next choices were.  If the next choice has already won
	  or been eliminated, it keeps going down the list until it finds a candidate still in the race.
