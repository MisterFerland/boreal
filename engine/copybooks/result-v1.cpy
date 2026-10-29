       01  calculation-result.
           05 result-reason               pic x(24).
              88 result-accepted          value 'ACCEPTED'.
           05 eligible-cost               pic s9(7)v99 comp-3.
           05 reimbursement-rate          pic 9v99 comp-3.
           05 unrounded-award             pic 9(9)v9(4) comp-3.
           05 rounded-award               pic 9(9)v99 comp-3.
           05 payable-award               pic 9(7)v99 comp-3.
           05 debit-account               pic x(4).
           05 credit-account              pic x(4).
