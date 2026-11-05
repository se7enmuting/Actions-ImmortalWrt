# Extracted unchanged from ImmortalWrt scripts/feeds at 4fc16f2985a358bd43bb522e43f05395fcbd6ed5.
# Upstream source: https://github.com/immortalwrt/immortalwrt/blob/4fc16f2985a358bd43bb522e43f05395fcbd6ed5/scripts/feeds
use strict;
use warnings;
my @feeds;
sub parse_file($$);
sub parse_file($$) {
	my ($fname, $existing) = @_;
	my $line = 0;
	my $fh;

	open $fh, $fname or return undef;
	while (<$fh>) {
		chomp;
		s/#.+$//;
		$line++;
		next unless /\S/;

		my ($type, $flags, $name, $urls) = m!^src-([\w\-]+)((?:\s+--\w+(?:=\S+)?)*)\s+(\w+)(?:\s+(\S.*))?$!;
		unless ($type && $name) {
			die "Syntax error in $fname, line $line\n";
		}

		if ($existing->{$name}++) {
			die "Duplicate feed name '$name' in '$fname' line: $line\n";
		}

		my @src = defined($urls) ? split /\s+/, $urls : ();
		push @src, '' if @src == 0;

		my %flags;
		if (defined $flags) {
			while ($flags =~ m!\s+--(\w+)(?:=(\S+))?!g) {
				$flags{$1} = defined($2) ? $2 : 1;
			}
		}

		if ($type eq "include") {
			parse_file($urls, $existing) or
			    die "Unable to open included file '$urls'";
			next;
		}

		push @feeds, ["src-$type", $name, \@src, \%flags];
	}
	close $fh;
	return 1;
}

parse_file($ARGV[0], {}) or die "missing configuration";
print join("\n", map { $_->[1] } @feeds), "\n";
