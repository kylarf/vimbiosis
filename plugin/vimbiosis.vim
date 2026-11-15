if exists('g:loaded_vimbiosis')
  finish
endif
let g:loaded_vimbiosis = 1

command! -nargs=+ -complete=shellcmd Agent call vimbiosis#agent#start(<q-args>, <q-mods>)
command! AgentAttach call vimbiosis#agent#attach()
command! AgentStatus call vimbiosis#agent#status()
command! AgentDetach call vimbiosis#agent#detach()
command! AgentFollow call vimbiosis#agent#follow()
