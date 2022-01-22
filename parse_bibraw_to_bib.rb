require 'anystyle/parser'
Dir.entries('bib/').each do |filename|
	if filename.end_with? '.bib.txt'
		inputfile = File.open('bib/'+filename, 'r').read
		outputfile = File.open('bib/'+filename[0..-5], 'w')

		inputfile.each_line do |line|
			puts line
		  outputfile.puts Anystyle.parse(line, :bibtex).to_s
		end

		outputfile.close

		FileUtils.rm('bib/'+filename)
	end
end
