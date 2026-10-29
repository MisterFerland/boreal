       >>source format free
identification division.
program-id. boreal-packed.
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
01 input-line pic x(10).
fd output-file.
01 output-line pic x(64).
working-storage section.
01 input-path pic x(256).
01 output-path pic x(256).
01 input-status pic xx.
01 output-status pic xx.
01 done-flag pic 9 value 0.
   88 done value 1.
01 amount-text pic x(11).
01 sign-character pic x.
procedure division.
    accept input-path from argument-value end-accept
    accept output-path from argument-value end-accept
    open input input-file
    if input-status not = '00' perform io-failure end-if
    open output output-file
    if output-status not = '00' perform io-failure end-if
    perform until done
        read input-file end-read
        evaluate input-status
          when '10' set done to true
          when '00' perform decode-one
          when other perform io-failure
        end-evaluate
    end-perform
    close input-file
    if input-status not = '00' perform io-failure end-if
    close output-file
    if output-status not = '00' perform io-failure end-if
    move 0 to return-code
    goback.
decode-one.
    move spaces to output-line
    evaluate true
      when input-line(1:9) is not numeric
        move 'ERROR|PACKED_DIGIT' to output-line
      when input-line(10:1) not = 'A' and not = 'B' and not = 'C'
        and not = 'D' and not = 'E' and not = 'F'
        move 'ERROR|PACKED_SIGN' to output-line
      when other
        if input-line(10:1) = 'B' or = 'D'
            move '-' to sign-character
        else
            move '+' to sign-character
        end-if
        string sign-character input-line(1:7) '.' input-line(8:2)
          into amount-text
        end-string
        string 'OK|' amount-text into output-line end-string
    end-evaluate
    write output-line end-write
    if output-status not = '00' perform io-failure end-if.
io-failure.
    display 'ENGINE_IO|' input-status '|' output-status upon syserr end-display
    move 74 to return-code
    stop run.
