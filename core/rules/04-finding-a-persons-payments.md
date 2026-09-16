# FINDING A PERSON'S PAYMENTS

A person can be in the payment system under an email that is not on their
contact record. Same person, two identities, two different emails. This is
normal, not an edge case. It is the single most common reason a paying
customer looks like they have never paid.

When anyone asks me about a person's payments, I run all four of these
before I answer, in this order:

1. The payment system, search by name
2. Open their CRM contact and collect every email and every
   phone number on it
3. The payment system, search by each of those emails
4. The payment system, search by phone

I do not stop because step 1 or step 3 came back empty. Empty at those steps
is the normal case for this exact problem.

If all four come back empty, I say all four came back empty and I name all
four.

The payment system and the CRM are named in `core/config/systems.md`.
