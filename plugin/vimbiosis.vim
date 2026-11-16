if exists('g:loaded_vimbiosis')
  finish
endif
let g:loaded_vimbiosis = 1

command! -nargs=+ -complete=shellcmd Vbio call vimbiosis#agent#start(<q-args>, <q-mods>)
command! VbioAttach call vimbiosis#agent#attach()
command! VbioStatus call vimbiosis#agent#status()
command! VbioDetach call vimbiosis#agent#detach()
command! VbioFollow call vimbiosis#agent#follow()
