       *> Exactly 73 bytes. Character fields are IBM-037, not ASCII.
       *> Packed amount is 9 digits + sign nibble, 5 bytes, scale 2.
       01  mixed-detail.
           05 mixed-source                pic x(8).
           05 mixed-reference             pic x(20).
           05 mixed-program               pic x(4).
           05 mixed-date                  pic x(8).
           05 mixed-amount                pic s9(7)v99 comp-3.
           05 mixed-beneficiary           pic x(28).
