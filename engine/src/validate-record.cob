       >>source format free
identification division.
program-id. validate-record.
data division.
working-storage section.
01 date-number binary-long.
01 character-index binary-long.
01 check-text pic x(28).
01 check-length binary-long.
linkage section.
copy 'detail-v1.cpy'.
01 duplicate-flag pic x.
copy 'result-v1.cpy'.
procedure division using legacy-detail duplicate-flag calculation-result.
    initialize calculation-result
    move 'ACCEPTED' to result-reason
    evaluate true
      when detail-kind not = 'D'
        move 'RECORD_TYPE' to result-reason
      when detail-source = spaces or detail-reference = spaces
        move 'IDENTITY_REQUIRED' to result-reason
      when detail-program not = 'CIR1'
        move 'PROGRAM_UNSUPPORTED' to result-reason
      when detail-date is not numeric
        move 'DATE_INVALID' to result-reason
      when detail-amount(1:1) not = '+' and not = '-'
        move 'AMOUNT_SYNTAX' to result-reason
      when detail-amount(2:7) is not numeric
        move 'AMOUNT_SYNTAX' to result-reason
      when detail-amount(9:1) not = '.'
        move 'AMOUNT_SYNTAX' to result-reason
      when detail-amount(10:2) is not numeric
        move 'AMOUNT_SYNTAX' to result-reason
    end-evaluate
    if not result-accepted goback end-if
    move function numval(detail-date) to date-number
    if function test-date-yyyymmdd(date-number) not = 0
        move 'DATE_INVALID' to result-reason
        goback
    end-if
    move detail-source to check-text
    move 8 to check-length
    perform check-identifier
    move detail-reference to check-text
    move 20 to check-length
    perform check-identifier
    if not result-accepted goback end-if
    compute eligible-cost = function numval(detail-amount)
      on size error move 'AMOUNT_OVERFLOW' to result-reason
    end-compute
    if not result-accepted goback end-if
    evaluate true
      when eligible-cost <= 0
        move 'COST_NOT_POSITIVE' to result-reason
      when duplicate-flag = 'Y'
        move 'DUPLICATE_REFERENCE' to result-reason
    end-evaluate
    goback.
check-identifier.
    perform varying character-index from 1 by 1
      until character-index > check-length
        if (check-text(character-index:1) < 'A' or > 'Z')
          and (check-text(character-index:1) < '0' or > '9')
          and check-text(character-index:1) not = '-' and not = '_'
          and check-text(character-index:1) not = space
            move 'IDENTITY_SYNTAX' to result-reason
        end-if
    end-perform.
end program validate-record.
