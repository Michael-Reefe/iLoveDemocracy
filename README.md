A simple discord app that allows you to set up smarter voting polls.
Options are Score Then Automatic Runoff (STAR) and ranked-choice Single Transferable Vote (STV).

To set up a poll, use the command `/newpoll [name] [choice1] [choice2] ... [time limit] [description] [winners] [poll_type]`.
The arguments are the poll name, choices, time limit (in hours), description, and number of winners.

To get a ballot for a poll, use the button that shows up when the poll is created, or use the command
`/getballot [name]`.

To close a poll manually, use the the button that shows up when the poll is created, or use the command
`/closepoll [name]`.
