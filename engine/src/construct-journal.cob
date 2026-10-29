       >>source format free
identification division.
program-id. construct-journal.
data division.
linkage section.
copy 'result-v1.cpy'.
procedure division using calculation-result.
    if result-accepted
        move '5100' to debit-account
        move '2100' to credit-account
    end-if
    goback.
end program construct-journal.
