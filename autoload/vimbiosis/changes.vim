let s:entries = []
let s:owner = 0
let s:marked = {}
let s:index = 0

highlight default link VimbiosisAdded DiffAdd
highlight default link VimbiosisChanged DiffChange
highlight default link VimbiosisDeleted DiffDelete

function! s:diff_char(kind, default) abort
  let l:char = get(g:, 'vimbiosis_diff_' . a:kind . '_char', a:default)
  return type(l:char) == v:t_string && strchars(l:char) == 1
        \ && l:char !~# '[[:cntrl:]]' && strdisplaywidth(l:char) == 1
        \ ? l:char : a:default
endfunction

function! vimbiosis#changes#clear(buffer) abort
  call s:clear_properties(a:buffer)
  if exists('*sign_unplace')
    call sign_unplace('Vimbiosis', {'buffer': a:buffer})
  endif
  call setbufvar(a:buffer, 'vimbiosis_hunks', [])
  if has_key(s:marked, a:buffer)
    call remove(s:marked, a:buffer)
  endif
endfunction

function! s:clear_properties(buffer) abort
  if has('textprop') && bufloaded(a:buffer)
    for l:type in ['VimbiosisRemoved', 'VimbiosisAddedMarker', 'VimbiosisAddedText',
          \ 'VimbiosisAddedFill', 'VimbiosisDeletedMarker', 'VimbiosisChangedMarker',
          \ 'VimbiosisPadding']
      if !empty(prop_type_get(l:type, {'bufnr': a:buffer}))
        call prop_remove({'bufnr': a:buffer, 'type': l:type, 'all': 1}, 1,
              \ len(getbufline(a:buffer, 1, '$')))
      endif
    endfor
  endif
endfunction

function! s:text_width(buffer) abort
  let l:windows = getwininfo()
  call filter(l:windows, 'v:val.bufnr == a:buffer')
  let l:width = &columns
  if !empty(l:windows)
    let l:window = l:windows[0]
    for l:info in l:windows
      if l:info.winid == win_getid()
        let l:window = l:info
        break
      endif
    endfor
    let l:width = max([1, l:window.width - l:window.textoff])
  endif
  return l:width
endfunction

function! s:removed_text(buffer, text, width, marker, padding) abort
  let l:text = a:marker
  " Inline markers count toward Vim's tab stops on live lines.
  let l:column = 1
  let l:tabstop = getbufvar(a:buffer, '&tabstop')
  let l:stops = map(split(getbufvar(a:buffer, '&vartabstop'), ','), 'str2nr(v:val)')
  for l:character in split(a:text, '\zs')
    if l:character ==# "\t"
      let l:remaining = l:column
      let l:step = l:tabstop
      for l:stop in l:stops
        let l:step = l:stop
        if l:remaining < l:step
          break
        endif
        let l:remaining -= l:step
      endfor
      let l:character = repeat(' ', l:step - l:remaining % l:step)
    elseif l:character =~# '[[:cntrl:]]'
      let l:character = ' '
    endif
    let l:text .= l:character
    let l:column += strdisplaywidth(l:character)
  endfor
  " Virtual text highlights only its characters, including trailing spaces.
  let l:width = a:width
  let l:rows = []
  let l:row = ''
  for l:character in split(l:text, '\zs')
    if strdisplaywidth(l:row . l:character) > l:width && !empty(l:row)
      call add(l:rows, l:row . repeat(a:padding, max([0, l:width - strdisplaywidth(l:row)])))
      let l:row = ''
    endif
    let l:row .= l:character
  endfor
  call add(l:rows, l:row . repeat(a:padding, max([0, l:width - strdisplaywidth(l:row)])))
  return l:rows
endfunction

function! vimbiosis#changes#resize() abort
  for l:buffer in keys(copy(s:marked))
    call vimbiosis#changes#paint(str2nr(l:buffer))
  endfor
endfunction

function! vimbiosis#changes#paint(buffer) abort
  call s:clear_properties(a:buffer)
  if !exists('*sign_place') || !bufloaded(a:buffer)
    return
  endif
  call sign_unplace('Vimbiosis', {'buffer': a:buffer})
  let l:virtual = get(g:, 'vimbiosis_enable_virtual_text', 1)
        \ && has('textprop') && has('patch-9.0.0438')
  let l:hunks = getbufvar(a:buffer, 'vimbiosis_hunks', [])
  if empty(l:hunks)
    return
  endif
  let l:add_char = s:diff_char('add', '+')
  let l:remove_char = s:diff_char('remove', '-')
  let l:change_char = s:diff_char('change', l:virtual ? l:add_char : '~')
  let l:padding_char = s:diff_char('padding', ' ')
  let l:marked_lines = {}
  let l:has_removals = 0
  if l:virtual && empty(prop_type_get('VimbiosisRemoved', {'bufnr': a:buffer}))
    call prop_type_add('VimbiosisRemoved', {'bufnr': a:buffer,
          \ 'highlight': 'VimbiosisDeleted'})
  endif
  if l:virtual
    let l:width = s:text_width(a:buffer)
    if empty(prop_type_get('VimbiosisPadding', {'bufnr': a:buffer}))
      call prop_type_add('VimbiosisPadding', {'bufnr': a:buffer})
    endif
    for l:type in ['AddedMarker', 'AddedText', 'AddedFill', 'DeletedMarker']
      if empty(prop_type_get('Vimbiosis' . l:type, {'bufnr': a:buffer}))
        call prop_type_add('Vimbiosis' . l:type, {'bufnr': a:buffer,
              \ 'highlight': l:type ==# 'DeletedMarker' ? 'VimbiosisDeleted' : 'VimbiosisAdded'})
      endif
    endfor
  else
    call sign_define('VimbiosisAdded', {'text': l:add_char, 'linehl': 'VimbiosisAdded'})
    call sign_define('VimbiosisChanged', {'text': l:change_char, 'linehl': 'VimbiosisChanged'})
    call sign_define('VimbiosisDeleted', {'text': l:remove_char, 'texthl': 'VimbiosisDeleted'})
  endif
  for l:hunk in l:hunks
    if l:virtual && !empty(get(l:hunk, 'removed_lines', []))
      let l:has_removals = 1
      for l:text in l:hunk.removed_lines
        for l:row in s:removed_text(a:buffer, l:text, l:width, l:remove_char, l:padding_char)
          call prop_add(l:hunk.line, 0, {'bufnr': a:buffer,
                \ 'type': 'VimbiosisRemoved', 'text': l:row,
                \ 'text_align': get(l:hunk, 'removed_placement', 'above'),
                \ 'text_wrap': 'truncate'})
        endfor
      endfor
      if l:hunk.kind ==# 'deleted'
        continue
      endif
    endif
    if l:hunk.kind ==# 'unknown'
      continue
    endif
    let l:kind = get({'added': 'Added', 'changed': 'Changed', 'deleted': 'Deleted'},
          \ l:hunk.kind, 'Changed')
    let l:last = l:hunk.kind ==# 'deleted' ? l:hunk.line : l:hunk.end_line
    for l:line in range(l:hunk.line, l:last)
      if l:virtual
        let l:marked_lines[l:line] = 1
        let l:added = l:kind !=# 'Deleted'
        let l:marker = l:kind ==# 'Changed' ? l:change_char :
              \ l:added ? l:add_char : l:remove_char
        call prop_add(l:line, 1, {'bufnr': a:buffer,
              \ 'type': l:added ? 'VimbiosisAddedMarker' : 'VimbiosisDeletedMarker',
              \ 'text': l:marker})
        if l:added
          let l:text = getbufline(a:buffer, l:line)[0]
          call prop_add(l:line, 1, {'bufnr': a:buffer, 'type': 'VimbiosisAddedText',
                \ 'length': max([1, strlen(l:text)])})
          let l:padding = (l:width - strdisplaywidth(l:marker . l:text) % l:width) % l:width
          if l:padding > 0
            call prop_add(l:line, 0, {'bufnr': a:buffer, 'type': 'VimbiosisAddedFill',
                  \ 'text': repeat(l:padding_char, l:padding), 'text_wrap': 'truncate'})
          endif
        endif
      else
        call sign_place(0, 'Vimbiosis', 'Vimbiosis' . l:kind, a:buffer,
              \ {'lnum': l:line, 'priority': 20})
      endif
    endfor
  endfor
  if l:has_removals || !empty(l:marked_lines)
    for l:line in range(1, getbufinfo(a:buffer)[0].linecount)
      if !has_key(l:marked_lines, l:line)
        call prop_add(l:line, 1, {'bufnr': a:buffer, 'type': 'VimbiosisPadding',
              \ 'text': l:padding_char})
      endif
    endfor
  endif
endfunction

function! vimbiosis#changes#enter() abort
  if &modified
    return
  endif
  if get(b:, 'vimbiosis_pending_reload', 0)
    let b:vimbiosis_pending_reload = 0
    silent keepalt edit
  endif
  call vimbiosis#changes#paint(bufnr('%'))
endfunction

function! vimbiosis#changes#record(change, window) abort
  let l:path = a:change.path
  call filter(s:entries, 'v:val.filename !=# l:path')
  let l:buf = bufnr(l:path)
  if l:buf >= 0
    call vimbiosis#changes#clear(l:buf)
    if !get(a:change, 'deleted', 0)
      call setbufvar(l:buf, 'vimbiosis_hunks', a:change.hunks)
      let s:marked[l:buf] = 1
      if !getbufvar(l:buf, 'vimbiosis_pending_reload', 0)
        call vimbiosis#changes#paint(l:buf)
      endif
    endif
  endif
  for l:hunk in a:change.hunks
    call add(s:entries, {'filename': l:path, 'lnum': l:hunk.line,
          \ 'end_lnum': l:hunk.end_line, 'col': 1, 'text': l:hunk.text})
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

function! vimbiosis#changes#show_if_multiple() abort
  if !get(g:, 'vimbiosis_auto_open_changes', 1)
    return
  endif
  let l:files = uniq(sort(map(copy(s:entries), 'v:val.filename')))
  if len(l:files) < 2 || empty(getwininfo(s:owner))
    return
  endif
  let l:current = win_getid()
  try
    if win_gotoid(s:owner) && getloclist(0, {'winid': 0}).winid == 0
      execute 'belowright lopen ' . min([5, len(s:entries)])
    endif
  finally
    call win_gotoid(l:current)
  endtry
endfunction

function! vimbiosis#changes#toggle() abort
  let l:current = win_getid()
  if !win_gotoid(s:owner)
    echomsg 'No agent changes to review'
    return
  endif
  if getloclist(0, {'winid': 0}).winid > 0
    lclose
    call win_gotoid(l:current)
  elseif empty(s:entries)
    call win_gotoid(l:current)
    echomsg 'No agent changes to review'
  else
    lopen
  endif
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
