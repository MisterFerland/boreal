       >>source format free
identification division.
program-id. boreal-reverse.
environment division.
input-output section.
file-control.
    select input-file assign to input-path
      organization line sequential file status input-status.
    select output-file assign to output-path
      organization line sequential file status output-status.
data division.
file section.
fd input-file.
01 input-line.
    05 original-debit pic x(4).
    05 original-credit pic x(4).
    05 original-amount pic x(11).
fd output-file.
01 output-line pic x(32).
working-storage section.
01 input-path pic x(256).
01 output-path pic x(256).
01 input-status pic xx.
01 output-status pic xx.
01 amount-value pic s9(7)v99 comp-3.
01 display-amount pic 9(7).99.
procedure division.
    accept input-path from argument-value end-accept
    accept output-path from argument-value end-accept
    open input input-file
    if input-status not = '00' perform io-failure end-if
    read input-file end-read
    if input-status not = '00' perform io-failure end-if
    if original-debit not = '5100' or original-credit not = '2100'
      or original-amount(1:1) not = '+'
      or original-amount(2:7) is not numeric
      or original-amount(9:1) not = '.'
      or original-amount(10:2) is not numeric
        move 65 to return-code stop run
    end-if
    compute amount-value = function numval(original-amount)
      on size error move 65 to return-code stop run
    end-compute
    if amount-value <= 0 or amount-value > 2500
        move 65 to return-code stop run
    end-if
    move amount-value to display-amount
    move spaces to output-line
    string original-credit '|' original-debit '|' display-amount
      into output-line
    end-string
    read input-file end-read
    if input-status not = '10'
        move 65 to return-code stop run
    end-if
    close input-file
    if input-status not = '00' perform io-failure end-if
    open output output-file
    if output-status not = '00' perform io-failure end-if
    write output-line end-write
    if output-status not = '00' perform io-failure end-if
    close output-file
    if output-status not = '00' perform io-failure end-if
    move 0 to return-code
    goback.
io-failure.
    display 'ENGINE_IO|' input-status '|' output-status upon syserr
    end-display
    move 74 to return-code
    stop run.
