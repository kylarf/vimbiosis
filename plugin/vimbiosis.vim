if exists('g:loaded_vimbiosis')
  finish
endif
let g:loaded_vimbiosis = 1

augroup vimbiosis_workspace
  autocmd!
  autocmd BufEnter,WinEnter,WinLeave * call vimbiosis#remember_window()
augroup END

command! -nargs=+ -complete=shellcmd Vbio call vimbiosis#agent#start(<q-args>, <q-mods>)
command! VbioAttach call vimbiosis#agent#attach()
command! VbioStatus call vimbiosis#agent#status()
command! VbioDetach call vimbiosis#agent#detach()
command! VbioFollow call vimbiosis#agent#follow()
command! VbioChanges call vimbiosis#changes#navigate('open')
command! VbioDiff call vimbiosis#changes#diff()
command! VbioDiffAll call vimbiosis#changes#diff_all()
command! VbioToggleChanges call vimbiosis#changes#toggle()
command! VbioNext call vimbiosis#changes#navigate('next')
command! VbioPrevious call vimbiosis#changes#navigate('previous')
command! VbioClear call vimbiosis#changes#clear(bufnr('%'))
command! VbioChangesClear call vimbiosis#changes#reset()

augroup vimbiosis_changes
  autocmd!
  autocmd BufWinEnter * call vimbiosis#changes#enter()
  autocmd InsertEnter * if bufnr('%') != get(t:, 'vimbiosis_review', 0) | call vimbiosis#changes#clear(bufnr('%')) | endif
  autocmd TabEnter,BufWinEnter * call vimbiosis#changes#review_update(0)
  if exists('##WinClosed')
    autocmd WinClosed * call vimbiosis#changes#review_update(str2nr(expand('<amatch>')))
  endif
  if exists('##WinResized')
    autocmd WinResized * call vimbiosis#changes#resize()
  endif
augroup END
