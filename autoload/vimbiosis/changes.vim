let s:entries = []
let s:owner = 0
let s:marked = {}
let s:index = 0

highlight default link VimbiosisAdded DiffAdd
highlight default link VimbiosisChanged DiffChange
highlight default link VimbiosisDeleted DiffDelete
if exists('*sign_define')
  call sign_define('VimbiosisAdded', {'text': '+', 'linehl': 'VimbiosisAdded'})
  call sign_define('VimbiosisChanged', {'text': '~', 'linehl': 'VimbiosisChanged'})
  call sign_define('VimbiosisDeleted', {'text': '-', 'texthl': 'VimbiosisDeleted'})
endif

function! vimbiosis#changes#clear(buffer) abort
  if exists('*sign_unplace')
    call sign_unplace('Vimbiosis', {'buffer': a:buffer})
  endif
  if has_key(s:marked, a:buffer)
    call remove(s:marked, a:buffer)
  endif
endfunction

function! vimbiosis#changes#record(change, window) abort
  let l:path = a:change.path
  call filter(s:entries, 'v:val.filename !=# l:path')
  let l:buf = bufnr(l:path)
  if l:buf >= 0
    call vimbiosis#changes#clear(l:buf)
  endif
  for l:hunk in a:change.hunks
    call add(s:entries, {'filename': l:path, 'lnum': l:hunk.line,
          \ 'end_lnum': l:hunk.end_line, 'col': 1, 'text': l:hunk.text})
    if l:buf < 0 || get(a:change, 'deleted', 0) || !exists('*sign_place')
      continue
    endif
    let l:kind = get({'added': 'Added', 'changed': 'Changed', 'deleted': 'Deleted'},
          \ l:hunk.kind, 'Changed')
    let l:last = l:hunk.kind ==# 'deleted' ? l:hunk.line : l:hunk.end_line
    for l:line in range(l:hunk.line, l:last)
      call sign_place(0, 'Vimbiosis', 'Vimbiosis' . l:kind, l:buf,
            \ {'lnum': l:line, 'priority': 20})
    endfor
    let s:marked[l:buf] = 1
  endfor
  let s:index = empty(s:entries) ? 0 : max([1, len(s:entries) - len(a:change.hunks) + 1])
  let l:owner = get(g:, 'vimbiosis_live_win', 0)
  if empty(getwininfo(l:owner))
    let l:owner = !empty(getwininfo(s:owner)) ? s:owner :
          \ (a:window > 0 ? a:window : win_getid())
  endif
  if l:owner != s:owner
    if !empty(getwininfo(s:owner))
      call win_execute(s:owner, 'call vimbiosis#changes#unown()')
    endif
    let s:owner = l:owner
  endif
  call win_execute(s:owner, 'call vimbiosis#changes#sync()')
  if a:window > 0 && a:window == get(g:, 'vimbiosis_live_win', 0)
        \ && !empty(a:change.hunks)
    call win_execute(a:window, 'call cursor(' . a:change.hunks[0].line . ', 1) | normal! zz')
  endif
endfunction

function! vimbiosis#changes#unown() abort
  let l:context = getloclist(0, {'context': 0}).context
  if type(l:context) == v:t_dict && get(l:context, 'vimbiosis', 0)
    call setloclist(0, [], 'r')
  endif
endfunction

function! vimbiosis#changes#sync() abort
  call setloclist(0, [], 'r', {'title': 'Agent changes', 'items': s:entries,
        \ 'idx': s:index, 'context': {'vimbiosis': 1}})
endfunction

function! vimbiosis#changes#navigate(action) abort
  if empty(s:entries) || !win_gotoid(s:owner)
    echomsg 'No agent changes to review'
    return
  endif
  if a:action ==# 'open'
    lopen
  elseif a:action ==# 'next'
    lnext
  elseif a:action ==# 'previous'
    lprevious
  endif
endfunction

function! vimbiosis#changes#reset() abort
  for l:buf in keys(copy(s:marked))
    call vimbiosis#changes#clear(str2nr(l:buf))
  endfor
  let s:entries = []
  let s:index = 0
  if !empty(getwininfo(s:owner))
    call win_execute(s:owner, 'call vimbiosis#changes#sync()')
  endif
endfunction
